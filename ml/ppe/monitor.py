"""Run compliance monitoring on a video file, webcam or stream.

    python -m ppe.monitor --source clip.mp4 --out outputs/clip      # file
    python -m ppe.monitor --source 0 --out outputs/webcam           # webcam (Ctrl+C to stop)
    python -m ppe.monitor --source rtsp://cam/stream --out outputs/cam1

Writes to ``--out``:
  annotated.mp4   H.264 (browser-playable) video with overlays
  events.jsonl    violation_started / violation_ended events
  frames.jsonl    per-frame summary (counts) — what the Live Monitor UI will consume
  snapshots/      one cropped JPEG per violation
  summary.json    totals for the run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import cv2

from ppe.compliance.draw import draw
from ppe.compliance.pipeline import ComplianceMonitor
from ppe.config import load_config, resolve


class H264Writer:
    """Pipe raw frames into ffmpeg -> H.264 MP4 (falls back to OpenCV mp4v)."""

    def __init__(self, path: Path, w: int, h: int, fps: float):
        self.proc = self.cv = None
        if shutil.which("ffmpeg"):
            self.proc = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                 "-s", f"{w}x{h}", "-r", f"{fps:.3f}", "-i", "-",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # H.264 4:2:0 needs even dimensions
                 "-c:v", "libx264", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
                stdin=subprocess.PIPE)
        else:
            self.cv = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    def write(self, frame):
        if self.proc:
            self.proc.stdin.write(frame.tobytes())
        else:
            self.cv.write(frame)

    def close(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait()
        else:
            self.cv.release()


def run(source: str, out: str, cfg: dict, stride: int = 1, max_seconds: float | None = None,
        save_video: bool = True, monitor: ComplianceMonitor | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        on_event: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None, verbose: bool = True) -> dict:
    """Process a video/stream. Callbacks let a caller (the API job worker) report
    progress ``(frames_read, total_frames)``, persist events as they happen, and cancel."""
    out_dir = resolve(out)
    (out_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    is_live = source.isdigit() or source.split(":", 1)[0] in {"rtsp", "rtmp", "http", "https"}
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise ValueError(f"Could not open source: {source}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if not 1 <= src_fps <= 240:
        src_fps = 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    monitor = monitor or ComplianceMonitor.from_config(cfg)
    writer = H264Writer(out_dir / "annotated.mp4", w, h, src_fps / stride) if save_video else None
    ev_f = open(out_dir / "events.jsonl", "w")
    fr_f = open(out_dir / "frames.jsonl", "w")

    def log_events(events, snaps=None):
        for e in events:
            rec = e.__dict__.copy()
            if snaps and e.event_id in snaps and e.type == "violation_started" and snaps[e.event_id].size:
                p = out_dir / "snapshots" / f"event_{e.event_id:04d}.jpg"
                cv2.imwrite(str(p), snaps[e.event_id])
                rec["snapshot"] = str(p.relative_to(out_dir))
            ev_f.write(json.dumps(rec) + "\n")
            if on_event:
                on_event(rec)
            if verbose:
                print(f"[{rec['t']:7.2f}s] {e.type:18s} worker #{e.worker_id}"
                  + (f"  ({e.duration_s:.1f}s, {e.reason})" if e.type == "violation_ended" else ""))

    n = processed = 0
    t0 = time.perf_counter()
    infer_s = 0.0
    peak = {"workers": 0, "violations": 0}
    t = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            n += 1
            if (n - 1) % stride:
                continue
            t = (time.perf_counter() - t0) if is_live else (n - 1) / src_fps
            if max_seconds and t > max_seconds:
                break
            if should_stop and should_stop():
                break
            s0 = time.perf_counter()
            res = monitor.process(frame, t)
            infer_s += time.perf_counter() - s0
            processed += 1
            log_events(res.events, res.snapshots)
            summ = res.summary
            for k in peak:
                peak[k] = max(peak[k], summ[k])
            fr_f.write(json.dumps({"t": round(t, 3), **summ}) + "\n")
            if writer:
                writer.write(draw(frame, res, fps=processed / infer_s if infer_s else None))
            if on_progress and processed % 10 == 1:
                on_progress(n, total)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        log_events(monitor.finish(t))
        cap.release()
        if writer:
            writer.close()
        ev_f.close()
        fr_f.close()

    events = [json.loads(l) for l in open(out_dir / "events.jsonl")]
    summary = {
        "source": source, "frames_read": n, "frames_processed": processed,
        "video_seconds": round(t, 2), "width": w, "height": h, "fps": round(src_fps, 2),
        "pipeline_fps": round(processed / infer_s, 1) if infer_s else None,
        "ms_per_frame": round(1000 * infer_s / processed, 1) if processed else None,
        "violations": sum(e["type"] == "violation_started" for e in events),
        "peak_workers_in_frame": peak["workers"], "peak_violations_in_frame": peak["violations"],
        "thresholds": monitor.conf, "device": monitor.device,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    if on_progress:
        on_progress(n, max(total, n))
    if verbose:
        print(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="video path, webcam index, or rtsp/http URL")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="configs/monitor.yaml")
    ap.add_argument("--ppe-model")
    ap.add_argument("--no-person", action="store_true", help="skip the COCO person model (faster)")
    ap.add_argument("--thresholds")
    ap.add_argument("--stride", type=int, default=1, help="process every Nth frame")
    ap.add_argument("--max-seconds", type=float)
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.ppe_model:
        cfg["ppe_model"] = a.ppe_model
    if a.no_person:
        cfg["person_model"] = None
    if a.thresholds:
        cfg["thresholds_file"] = a.thresholds
    run(a.source, a.out, cfg, a.stride, a.max_seconds, not a.no_video)


if __name__ == "__main__":
    main()
