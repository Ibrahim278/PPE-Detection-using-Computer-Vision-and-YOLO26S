from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import ViolationEvent, engine

router = APIRouter(prefix="/events", tags=["events"])


def event_out(e: ViolationEvent) -> dict:
    d = e.model_dump()
    d["snapshot_url"] = f"/media/{e.snapshot}" if e.snapshot else None
    return d


@router.get("")
def list_events(source: str | None = None, source_id: str | None = None, status: str | None = None,
                since: datetime | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """Violation events across video jobs and live streams, newest first."""
    q = select(ViolationEvent)
    if source:
        q = q.where(ViolationEvent.source == source)
    if source_id:
        q = q.where(ViolationEvent.source_id == source_id)
    if status:
        q = q.where(ViolationEvent.status == status)
    if since:
        q = q.where(ViolationEvent.created_at >= since)
    q = q.order_by(ViolationEvent.created_at.desc(), ViolationEvent.id.desc()).offset(offset).limit(min(limit, 500))
    with Session(engine) as s:
        return [event_out(e) for e in s.exec(q).all()]


@router.get("/summary")
def events_summary() -> dict:
    """Totals for the dashboard header."""
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    with Session(engine) as s:
        total = s.exec(select(func.count()).select_from(ViolationEvent)).one()
        open_ = s.exec(select(func.count()).select_from(ViolationEvent).where(ViolationEvent.status == "open")).one()
        last_24h = s.exec(select(func.count()).select_from(ViolationEvent)
                          .where(ViolationEvent.created_at >= day_ago)).one()
        by_source = dict(s.exec(select(ViolationEvent.source, func.count()).group_by(ViolationEvent.source)).all())
        avg = s.exec(select(func.avg(ViolationEvent.duration_s))).one()
    return {"total": total, "open": open_, "last_24h": last_24h, "by_source": by_source,
            "avg_duration_s": round(avg, 2) if avg else None}
