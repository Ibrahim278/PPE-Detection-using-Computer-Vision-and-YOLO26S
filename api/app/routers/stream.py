"""Live monitoring over WebSocket.

Protocol (``ws://<host>/api/stream``):
  server -> {"type": "ready", "session_id", "thresholds", ...}
  client -> binary JPEG frame            (repeat; the n-th frame sent has frame_id n)
  server -> {"type": "frame", "frame_id", "t", "width", "height", "summary",
             "workers", "unverified", "events", "latency_ms", "dropped"}
  server -> {"type": "error", "message"}  (bad frame; the stream continues)

Encode frames as JPEG quality ~0.92 (or WebP ~0.9) at the camera's native size (640-1280 px
wide). Heavier compression can push borderline bare-head detections under the threshold.

The server always processes the *newest* frame and drops older unprocessed ones,
so latency never builds up. Clients should draw boxes for ``frame_id`` on a
canvas over their own <video>; only JSON comes back.
"""

from __future__ import annotations

import asyncio
import time

import anyio
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import record_event
from app.runtime import new_monitor
from app.settings import settings

router = APIRouter(tags=["stream"])

MAX_FRAME_BYTES = 4 * 1024 * 1024
_slots = asyncio.Semaphore(settings.max_streams)


@router.websocket("/stream")
async def stream(ws: WebSocket, source: str = "webcam") -> None:
    await ws.accept()
    if _slots.locked():
        await ws.send_json({"type": "error", "message": "Server is busy: too many live streams."})
        await ws.close(code=1013)
        return
    async with _slots:
        await _serve(ws, source[:64])


async def _serve(ws: WebSocket, source: str) -> None:
    sid = uuid.uuid4().hex[:12]
    snap_dir = settings.streams_dir / sid
    monitor = await anyio.to_thread.run_sync(new_monitor)
    t0 = time.monotonic()
    await ws.send_json({"type": "ready", "session_id": sid, "source": source, "thresholds": monitor.conf,
                        "smoothing": {"min_violation_s": monitor.state.min_violation_s,
                                      "resolve_s": monitor.state.resolve_s}})

    latest: list = [0, None]          # [frame_id, bytes]
    new_frame = asyncio.Event()

    def save_events(events, snapshots) -> list[dict]:
        out = []
        for e in events:
            rec = dict(e.__dict__)
            snap = None
            if e.type == "violation_started" and e.event_id in snapshots and snapshots[e.event_id].size:
                snap_dir.mkdir(parents=True, exist_ok=True)
                path = snap_dir / f"event_{e.event_id:04d}.jpg"
                cv2.imwrite(str(path), snapshots[e.event_id])
                snap = f"streams/{sid}/{path.name}"
            record_event("stream", sid, rec, snap)
            rec["snapshot_url"] = f"/media/{snap}" if snap else None
            out.append(rec)
        return out

    def handle(data: bytes, t: float):
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None, None
        res = monitor.process(img, t)
        return img.shape, (res, save_events(res.events, res.snapshots))

    async def receiver(scope: anyio.CancelScope) -> None:
        received = 0
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                scope.cancel()          # stop the processor too
                return
            data = msg.get("bytes")
            if data is None:
                continue  # text messages (e.g. pings) are ignored
            received += 1
            latest[0], latest[1] = received, data
            new_frame.set()

    async def processor() -> None:
        last_id = 0
        while True:
            await new_frame.wait()
            new_frame.clear()
            fid, data = latest[0], latest[1]
            dropped, last_id = fid - last_id - 1, fid
            if len(data) > MAX_FRAME_BYTES:
                await ws.send_json({"type": "error", "frame_id": fid, "message": "Frame too large (max 4 MB)."})
                continue
            s = time.perf_counter()
            # run_sync waits for the thread even if cancelled, so the monitor is never
            # used by two threads at once (and cleanup below runs after the last frame).
            shape, out = await anyio.to_thread.run_sync(handle, data, time.monotonic() - t0)
            if out is None:
                await ws.send_json({"type": "error", "frame_id": fid, "message": "Frame is not a valid JPEG/PNG."})
                continue
            res, events = out
            j = res.to_json()
            j["events"] = events
            await ws.send_json({"type": "frame", "frame_id": fid, "width": shape[1], "height": shape[0],
                                "latency_ms": round((time.perf_counter() - s) * 1000, 1),
                                "dropped": max(0, dropped), **j})

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(receiver, tg.cancel_scope)
            tg.start_soon(processor)
    except WebSocketDisconnect:
        pass
    finally:
        # Close any open violations for this session (synchronous: safe even if we're being cancelled).
        for e in monitor.finish(time.monotonic() - t0):
            record_event("stream", sid, dict(e.__dict__))
