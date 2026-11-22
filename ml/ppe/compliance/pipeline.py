"""Frame-by-frame compliance monitoring.

Two models run per frame:
  * the PPE model (helmet / head), *tracked* with ByteTrack. Each head-region
    track is one worker; its class flips between helmet and head as status changes.
  * an optional COCO model for ``person``. Person boxes are associated with
    head tracks; a person with no visible head counts as an "unverified" worker
    (back turned, occluded), so the worker count isn't just the head count.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ppe.compliance.association import associate_heads_to_persons
from ppe.compliance.state import ComplianceTracker, Event, Observation
from ppe.config import get_device, resolve


@dataclass
class WorkerView:
    id: int
    status: str
    box: list[float]
    conf: float
    violation_s: float = 0.0
    person_box: list[float] | None = None


@dataclass
class FrameResult:
    t: float
    workers: list[WorkerView]
    unverified: list[list[float]]
    events: list[Event]
    snapshots: dict[int, np.ndarray] = field(default_factory=dict)   # event_id -> BGR crop

    @property
    def summary(self) -> dict[str, int]:
        s = {"workers": len(self.workers) + len(self.unverified), "compliant": 0,
             "at_risk": 0, "violations": 0, "unverified": len(self.unverified)}
        for w in self.workers:
            s["violations" if w.status == "violation" else w.status] += 1
        return s

    def to_json(self) -> dict:
        return {
            "t": round(self.t, 3),
            "summary": self.summary,
            "workers": [w.__dict__ for w in self.workers],
            "unverified": self.unverified,
            "events": [e.__dict__ for e in self.events],
        }


def _crop(frame: np.ndarray, box, pad: float = 0.25) -> np.ndarray:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = int(max(0, x1 - px)), int(max(0, y1 - py))
    x2, y2 = int(min(w, x2 + px)), int(min(h, y2 + py))
    return frame[y1:y2, x1:x2].copy()


class ComplianceMonitor:
    def __init__(self, ppe_model: str, person_model: str | None = "yolo26s.pt",
                 conf: dict[str, float] | None = None, person_conf: float = 0.4,
                 thresholds_file: str | None = None, tracker: str = "bytetrack.yaml",
                 imgsz: int = 640, device: str | None = None, display_grace_s: float = 0.5,
                 **smoothing):
        from ultralytics import YOLO

        self.device = get_device(device)
        self.imgsz = imgsz
        self.display_grace_s = display_grace_s
        self.tracker_cfg = tracker
        self.ppe = YOLO(str(resolve(ppe_model)))
        names = {v: k for k, v in self.ppe.names.items()}
        self.helmet_id, self.head_id = names["helmet"], names["head"]
        self.conf = {"helmet": 0.4, "head": 0.4, **(conf or {})}
        if thresholds_file:
            tuned = json.loads(Path(resolve(thresholds_file)).read_text())
            self.conf.update({k: v["conf"] for k, v in tuned.items() if k in self.conf})
        self.person = YOLO(str(person_model)) if person_model else None
        self.person_conf = person_conf
        self.state = ComplianceTracker(**smoothing)

    @classmethod
    def from_config(cls, cfg: dict, **overrides) -> "ComplianceMonitor":
        keys = ["ppe_model", "person_model", "conf", "person_conf", "thresholds_file", "tracker",
                "imgsz", "device", "display_grace_s", "min_violation_s", "resolve_s", "lost_s", "ema_alpha"]
        kw = {k: cfg[k] for k in keys if k in cfg}
        kw.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**kw)

    def reset(self) -> None:
        """Forget tracks (call between unrelated videos)."""
        self.state = ComplianceTracker(self.state.min_violation_s, self.state.resolve_s,
                                       self.state.lost_s, self.state.ema_alpha)
        if getattr(self.ppe, "predictor", None) is not None:
            for trk in getattr(self.ppe.predictor, "trackers", []) or []:
                trk.reset()

    def process(self, frame: np.ndarray, t: float) -> FrameResult:
        r = self.ppe.track(frame, persist=True, tracker=self.tracker_cfg, imgsz=self.imgsz,
                           conf=min(self.conf["helmet"], self.conf["head"]),
                           classes=[self.helmet_id, self.head_id], device=self.device, verbose=False)[0]
        heads = []
        if r.boxes is not None and r.boxes.id is not None:
            for box, cls, conf, tid in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                           r.boxes.conf.tolist(), r.boxes.id.tolist()):
                is_head = int(cls) == self.head_id
                if conf >= self.conf["head" if is_head else "helmet"]:
                    heads.append((int(tid), is_head, float(conf), tuple(box)))

        persons: list[list[float]] = []
        if self.person is not None:
            pr = self.person.predict(frame, classes=[0], conf=self.person_conf, imgsz=self.imgsz,
                                     device=self.device, verbose=False)[0]
            persons = pr.boxes.xyxy.tolist() if pr.boxes is not None else []
        match = associate_heads_to_persons([h[3] for h in heads], persons)

        obs = [Observation(tid, is_head, conf, box,
                           tuple(persons[match[i]]) if i in match else None)
               for i, (tid, is_head, conf, box) in enumerate(heads)]
        events = self.state.update(t, obs)

        # Show workers seen in the last `display_grace_s`, and keep open violations
        # on screen until the track is dropped, so one missed detection doesn't
        # make a worker (or a violation) blink out of the count.
        shown = [w for w in self.state.workers.values()
                 if t - w.last_seen <= self.display_grace_s or w.status == "violation"]
        workers = [WorkerView(w.track_id, w.status, [round(v, 1) for v in w.box], round(w.conf, 3),
                              round(w.violation_s(t), 2),
                              [round(v, 1) for v in w.person_box] if w.person_box else None)
                   for w in shown]
        matched = set(associate_heads_to_persons([w.box for w in shown], persons).values())
        unverified = [[round(v, 1) for v in p] for i, p in enumerate(persons) if i not in matched]

        snaps = {}
        for e in events:
            if e.type == "violation_started":
                w = self.state.workers.get(e.worker_id)
                snaps[e.event_id] = _crop(frame, w.person_box or e.box if w else e.box)
        return FrameResult(t, workers, unverified, events, snaps)

    def detect(self, frame: np.ndarray) -> FrameResult:
        """Single-image detection: no tracking or smoothing.

        A bare head is reported as a violation straight away and worker ids are
        just indices. Use a separate ComplianceMonitor instance from the one
        doing ``process()`` (tracking registers callbacks on the model).
        """
        r = self.ppe.predict(frame, imgsz=self.imgsz, conf=min(self.conf["helmet"], self.conf["head"]),
                             classes=[self.helmet_id, self.head_id], device=self.device, verbose=False)[0]
        heads = []
        if r.boxes is not None:
            for box, cls, conf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                is_head = int(cls) == self.head_id
                if conf >= self.conf["head" if is_head else "helmet"]:
                    heads.append((is_head, float(conf), box))
        persons: list[list[float]] = []
        if self.person is not None:
            pr = self.person.predict(frame, classes=[0], conf=self.person_conf, imgsz=self.imgsz,
                                     device=self.device, verbose=False)[0]
            persons = pr.boxes.xyxy.tolist() if pr.boxes is not None else []
        match = associate_heads_to_persons([h[2] for h in heads], persons)
        workers = [WorkerView(i + 1, "violation" if is_head else "compliant", [round(v, 1) for v in box],
                              round(conf, 3), 0.0,
                              [round(v, 1) for v in persons[match[i]]] if i in match else None)
                   for i, (is_head, conf, box) in enumerate(heads)]
        matched = set(match.values())
        unverified = [[round(v, 1) for v in p] for i, p in enumerate(persons) if i not in matched]
        return FrameResult(0.0, workers, unverified, [])

    def finish(self, t: float) -> list[Event]:
        return self.state.close_all(t)
