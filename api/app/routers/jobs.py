import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from app.db import Job, ViolationEvent, engine
from app.routers.events import event_out
from app.services import media, urls
from app.services.jobs import delete_job_data, job_dir, runner
from app.settings import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

ACTIVE = {"queued", "downloading", "processing"}


def job_out(job: Job) -> dict:
    d = job.model_dump()
    d["video_url"] = f"/media/jobs/{job.id}/annotated.mp4" if job.status in ("done", "cancelled") else None
    return d


def _get(job_id: str) -> Job:
    with Session(engine) as s:
        job = s.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return job


@router.post("", status_code=202)
async def create_job(file: UploadFile | None = File(None), url: str | None = Form(None),
                     start: str | None = Form(None), end: str | None = Form(None)) -> dict:
    """Start a video job from an uploaded file **or** a URL (direct video link, YouTube or Vimeo).

    Optional ``start`` / ``end`` (seconds or mm:ss / hh:mm:ss) analyse just that section.
    Poll ``GET /api/jobs/{id}`` for status and progress.
    """
    if bool(file and file.filename) == bool(url and url.strip()):
        raise HTTPException(422, "Send either a file or a url, not both.")
    try:
        start_s, end_s = media.parse_timestamp(start), media.parse_timestamp(end)
    except media.MediaError as e:
        raise HTTPException(422, str(e))
    if start_s is not None and end_s is not None and end_s <= start_s:
        raise HTTPException(422, "End time must be after the start time.")

    if url:
        url = url.strip()
        if not urls.is_platform_url(url):
            try:  # fail fast on obviously bad / private URLs; re-checked when downloading
                await run_in_threadpool(urls.resolve_target, url, settings.allow_private_urls)
            except urls.UrlError as e:
                raise HTTPException(422, str(e))
        elif not settings.enable_platform_urls:
            raise HTTPException(422, "YouTube/Vimeo links are disabled on this server.")
        job = Job(source_type="url", source_name=url[:500], start_s=start_s, end_s=end_s)
    else:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in media.VIDEO_EXTS:
            raise HTTPException(415, f"Unsupported file type '{ext or '?'}'. Use: "
                                     + ", ".join(sorted(media.VIDEO_EXTS)))
        job = Job(source_type="upload", source_name=file.filename[:255], start_s=start_s, end_s=end_s)

    d = job_dir(job.id)
    d.mkdir(parents=True, exist_ok=True)
    upload_path = None
    if file is not None and file.filename:
        limit = int(settings.max_upload_mb * 1024 * 1024)
        upload_path = d / f"input{ext}"
        size = 0
        with open(upload_path, "wb") as f:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    f.close()
                    upload_path.unlink(missing_ok=True)
                    d.rmdir()
                    raise HTTPException(413, f"File larger than {settings.max_upload_mb:g} MB.")
                f.write(chunk)

    with Session(engine) as s:
        s.add(job)
        s.commit()
        s.refresh(job)
    runner.submit(job.id, upload=upload_path, url=url)
    return job_out(job)


@router.get("")
def list_jobs(limit: int = 50, offset: int = 0) -> list[dict]:
    with Session(engine) as s:
        jobs = s.exec(select(Job).order_by(Job.created_at.desc()).offset(offset).limit(min(limit, 200))).all()
    return [job_out(j) for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = _get(job_id)
    out = job_out(job)
    with Session(engine) as s:
        evs = s.exec(select(ViolationEvent).where(ViolationEvent.source == "job",
                                                  ViolationEvent.source_id == job_id)
                     .order_by(ViolationEvent.started_at_s)).all()
    out["events"] = [event_out(e) for e in evs]
    return out


@router.get("/{job_id}/timeline")
def job_timeline(job_id: str, max_points: int = 1500) -> list[dict]:
    """Per-frame counts (t, workers, compliant, at_risk, violations, unverified), downsampled for charts."""
    _get(job_id)
    p = job_dir(job_id) / "frames.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    step = max(1, len(rows) // max(1, max_points))
    return rows[::step]


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    job = _get(job_id)
    if job.status not in ACTIVE:
        raise HTTPException(409, f"Job is already {job.status}.")
    runner.cancel(job_id)
    return {"id": job_id, "status": "cancelling"}


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    job = _get(job_id)
    if job.status in ACTIVE:
        raise HTTPException(409, "Cancel the job before deleting it.")
    delete_job_data(job_id)
