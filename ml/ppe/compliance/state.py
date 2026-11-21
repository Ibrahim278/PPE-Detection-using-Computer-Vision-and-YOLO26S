"""Temporal smoothing of per-worker helmet status and violation events.

Single frames are noisy: a head turning away can flip ``helmet`` -> ``head`` for
a frame or two. Each tracked worker keeps an exponential moving average of
P(bare head). A violation *opens* only after the smoothed status has been
"bare" for ``min_violation_s`` and *closes* after "helmet" for ``resolve_s`` or
when the worker has been gone for ``lost_s``. One continuous violation is one
event, however many frames it spans.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Literal

Status = Literal["compliant", "at_risk", "violation"]


@dataclass
class Observation:
    track_id: int
    is_head: bool                     # True = bare head, False = helmet
    conf: float
    box: tuple[float, float, float, float]
    person_box: tuple[float, float, float, float] | None = None


@dataclass
class Event:
    type: Literal["violation_started", "violation_ended"]
    event_id: int
    worker_id: int
    t: float
    started_at: float
    duration_s: float = 0.0
    reason: str | None = None        # for violation_ended: helmet_on | lost | stopped
    box: tuple[float, float, float, float] | None = None
    conf: float | None = None


@dataclass
class WorkerState:
    track_id: int
    first_seen: float
    last_seen: float
    p_head: float
    status: Status = "compliant"
    bare_since: float | None = None
    helmet_since: float | None = None
    event_id: int | None = None
    violation_started_at: float | None = None
    box: tuple[float, float, float, float] | None = None
    person_box: tuple[float, float, float, float] | None = None
    conf: float = 0.0

    def violation_s(self, now: float) -> float:
        return now - self.violation_started_at if self.violation_started_at is not None else 0.0


@dataclass
class ComplianceTracker:
    min_violation_s: float = 1.5
    resolve_s: float = 1.0
    lost_s: float = 2.0
    ema_alpha: float = 0.3
    workers: dict[int, WorkerState] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def update(self, t: float, observations: list[Observation]) -> list[Event]:
        events: list[Event] = []
        for ob in observations:
            x = 1.0 if ob.is_head else 0.0
            w = self.workers.get(ob.track_id)
            if w is None:
                w = self.workers[ob.track_id] = WorkerState(ob.track_id, t, t, x)
            else:
                w.p_head = self.ema_alpha * x + (1 - self.ema_alpha) * w.p_head
            w.last_seen, w.box, w.person_box, w.conf = t, ob.box, ob.person_box, ob.conf

            if w.p_head > 0.5:  # smoothed: bare head
                w.helmet_since = None
                w.bare_since = w.bare_since if w.bare_since is not None else t
                if w.status != "violation":
                    if t - w.bare_since >= self.min_violation_s:
                        w.status, w.violation_started_at, w.event_id = "violation", w.bare_since, next(self._ids)
                        events.append(Event("violation_started", w.event_id, w.track_id, t, w.bare_since,
                                            t - w.bare_since, box=w.box, conf=w.conf))
                    else:
                        w.status = "at_risk"
            else:  # smoothed: helmet
                w.bare_since = None
                w.helmet_since = w.helmet_since if w.helmet_since is not None else t
                if w.status == "violation":
                    if t - w.helmet_since >= self.resolve_s:
                        events.append(self._close(w, t, "helmet_on", end=w.helmet_since))
                else:
                    w.status = "compliant"

        for tid in [tid for tid, w in self.workers.items() if t - w.last_seen > self.lost_s]:
            w = self.workers.pop(tid)
            if w.status == "violation":
                events.append(self._close(w, t, "lost", end=w.last_seen))
        return events

    def close_all(self, t: float) -> list[Event]:
        """Close any open violations (end of video / stream stopped)."""
        events = [self._close(w, t, "stopped") for w in self.workers.values() if w.status == "violation"]
        self.workers.clear()
        return events

    def _close(self, w: WorkerState, t: float, reason: str, end: float | None = None) -> Event:
        end = t if end is None else end
        ev = Event("violation_ended", w.event_id, w.track_id, t, w.violation_started_at,
                   end - w.violation_started_at, reason=reason, box=w.box, conf=w.conf)
        w.status, w.event_id, w.violation_started_at = "compliant", None, None
        return ev
