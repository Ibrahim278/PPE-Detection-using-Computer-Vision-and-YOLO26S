"""ffprobe / ffmpeg helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg"}


class MediaError(ValueError):
    pass


def parse_timestamp(value: str | float | None) -> float | None:
    """'1:20:45' / '3:45' / '225' / '225.5' -> seconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    v = value.strip()
    if not re.fullmatch(r"\d+(\.\d+)?|(\d+:)?\d{1,2}:\d{1,2}(\.\d+)?", v):
        raise MediaError(f"Invalid time '{value}'. Use seconds or mm:ss / hh:mm:ss.")
    secs = 0.0
    for part in v.split(":"):
        secs = secs * 60 + float(part)
    return secs


def probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise MediaError("File is not a readable video.")
    data = json.loads(r.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("File has no video stream.")
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    return {"duration": duration, "width": video.get("width"), "height": video.get("height"),
            "codec": video.get("codec_name")}


def trim(src: Path, dst: Path, start: float | None, end: float | None) -> Path:
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += ["-i", str(src), "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(dst)]
    # -ss/-to before -i: fast seek; -to is then relative to the original timeline
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not dst.exists():
        raise MediaError("Could not cut the requested section of the video.")
    return dst
