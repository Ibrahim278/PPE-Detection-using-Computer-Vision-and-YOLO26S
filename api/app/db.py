"""SQLite persistence for video jobs and violation events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    finished_at: datetime | None = None
    source_type: str                     # upload | url
    source_name: str                     # original filename or URL
    start_s: float | None = None
    end_s: float | None = None
    status: str = "queued"               # queued | downloading | processing | done | failed | cancelled
    progress: float = 0.0                # 0..1
    error: str | None = None
    summary: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class ViolationEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)      # job | stream
    source_id: str = Field(index=True)   # job id or stream session id
    event_id: int                        # per-source event counter from the tracker
    worker_id: int
    started_at_s: float                  # seconds into the video / stream
    ended_at_s: float | None = None
    duration_s: float | None = None
    end_reason: str | None = None        # helmet_on | lost | stopped
    conf: float | None = None
    box: list[float] | None = Field(default=None, sa_column=Column(JSON))
    snapshot: str | None = None          # path relative to storage_dir
    status: str = Field(default="open", index=True)   # open | closed
    created_at: datetime = Field(default_factory=utcnow, index=True)


engine = create_engine(settings.db_url, connect_args={"check_same_thread": False}
                       if settings.db_url.startswith("sqlite") else {})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Jobs interrupted by a restart can't resume: mark them failed.
    with Session(engine) as s:
        for job in s.exec(select(Job).where(Job.status.in_(["queued", "downloading", "processing"]))):
            job.status, job.error, job.finished_at = "failed", "server restarted", utcnow()
            s.add(job)
        for ev in s.exec(select(ViolationEvent).where(ViolationEvent.status == "open")):
            ev.status, ev.end_reason = "closed", ev.end_reason or "stopped"
            s.add(ev)
        s.commit()


def record_event(source: str, source_id: str, rec: dict, snapshot: str | None = None) -> None:
    """Insert on violation_started, close the row on violation_ended."""
    with Session(engine) as s:
        if rec["type"] == "violation_started":
            s.add(ViolationEvent(source=source, source_id=source_id, event_id=rec["event_id"],
                                 worker_id=rec["worker_id"], started_at_s=rec["started_at"],
                                 conf=rec.get("conf"), box=list(rec["box"]) if rec.get("box") else None,
                                 snapshot=snapshot))
        else:
            ev = s.exec(select(ViolationEvent).where(ViolationEvent.source == source,
                                                     ViolationEvent.source_id == source_id,
                                                     ViolationEvent.event_id == rec["event_id"])).first()
            if ev is None:
                return
            ev.status, ev.end_reason = "closed", rec.get("reason")
            ev.duration_s = rec.get("duration_s")
            ev.ended_at_s = rec["started_at"] + (rec.get("duration_s") or 0.0)
            s.add(ev)
        s.commit()


def to_jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))
