"""Background video jobs: ingest -> (trim) -> compliance run -> results.

One worker thread, so jobs queue up and never fight over the GPU.
"""

from __future__ import annotations

import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ppe.monitor import run
from sqlmodel import Session, delete, select

from app.db import Job, ViolationEvent, engine, record_event, utcnow
from app.runtime import monitor_config, new_monitor
from app.services import media, urls
from app.settings import settings

log = logging.getLogger("ppe.jobs")


def job_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def _update(job_id: str, **fields) -> None:
    with Session(engine) as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        s.add(job)
        s.commit()


class JobRunner:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ppe-job")
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def submit(self, job_id: str, *, upload: Path | None = None, url: str | None = None) -> None:
        self._pool.submit(self._run_safe, job_id, upload, url)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            self._cancelled.add(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def _run_safe(self, job_id: str, upload: Path | None, url: str | None) -> None:
        try:
            self._run(job_id, upload, url)
        except (urls.UrlError, media.MediaError, ValueError) as e:
            _update(job_id, status="failed", error=str(e), finished_at=utcnow())
        except Exception:
            log.exception("job %s crashed", job_id)
            _update(job_id, status="failed", error="Internal error while processing the video.",
                    finished_at=utcnow())
        finally:
            with self._lock:
                self._cancelled.discard(job_id)

    def _run(self, job_id: str, upload: Path | None, url: str | None) -> None:
        if self.is_cancelled(job_id):
            _update(job_id, status="cancelled", finished_at=utcnow())
            return
        with Session(engine) as s:
            job = s.get(Job, job_id)
            start, end = job.start_s, job.end_s
        d = job_dir(job_id)
        max_bytes = int(settings.max_upload_mb * 1024 * 1024)

        # 1. Ingest
        trimmed_by_download = False
        if url:
            _update(job_id, status="downloading")
            if urls.is_platform_url(url):
                if not settings.enable_platform_urls:
                    raise urls.UrlError("YouTube/Vimeo links are disabled on this server.")
                src = urls.download_platform(url, d / "input", max_bytes, settings.max_video_seconds, start, end)
                trimmed_by_download = start is not None or end is not None
            else:
                src = urls.download_direct(url, d / "input.mp4", max_bytes, settings.download_timeout_s,
                                           settings.allow_private_urls)
        else:
            src = upload

        # 2. Validate + optional trim
        info = media.probe(src)
        if not trimmed_by_download and (start is not None or end is not None):
            if start is not None and info["duration"] and start >= info["duration"]:
                raise media.MediaError(f"Start time is past the end of the video ({info['duration']:.1f} s).")
            src = media.trim(src, d / "clip.mp4", start, end)
            info = media.probe(src)
        if info["duration"] > settings.max_video_seconds + 1:
            raise media.MediaError(f"Video is {info['duration']:.0f} s long; the limit is "
                                   f"{settings.max_video_seconds:g} s. Pick a start and end time.")

        # 3. Compliance run
        _update(job_id, status="processing", progress=0.0)

        def on_progress(read: int, total: int) -> None:
            if total:
                _update(job_id, progress=round(min(read / total, 1.0), 3))

        def on_event(rec: dict) -> None:
            snap = rec.get("snapshot")
            record_event("job", job_id, rec, f"jobs/{job_id}/{snap}" if snap else None)

        summary = run(str(src), str(d), monitor_config(), monitor=new_monitor(), on_progress=on_progress,
                      on_event=on_event, should_stop=lambda: self.is_cancelled(job_id), verbose=False)
        summary["source"] = None  # don't leak server paths
        summary["input"] = info

        # Keep outputs, drop the (possibly large) input files.
        for f in d.glob("input*"):
            f.unlink(missing_ok=True)
        (d / "clip.mp4").unlink(missing_ok=True)

        status = "cancelled" if self.is_cancelled(job_id) else "done"
        _update(job_id, status=status, progress=1.0 if status == "done" else None, summary=summary,
                finished_at=utcnow())


runner = JobRunner()


def delete_job_data(job_id: str) -> None:
    shutil.rmtree(job_dir(job_id), ignore_errors=True)
    with Session(engine) as s:
        s.exec(delete(ViolationEvent).where(ViolationEvent.source == "job", ViolationEvent.source_id == job_id))
        job = s.get(Job, job_id)
        if job:
            s.delete(job)
        s.commit()
