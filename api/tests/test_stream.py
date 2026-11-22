import cv2

from conftest import DEMO_CLIP


def jpeg_frames(path, start_s=0.0, seconds=4.0):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * fps))
    for _ in range(int(seconds * fps)):
        ok, frame = cap.read()
        if not ok:
            break
        yield cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()
    cap.release()


def test_stream_lockstep_detects_bare_head_and_records_event(client):
    with client.websocket_connect("/api/stream?source=test-cam") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["session_id"]
        sid = ready["session_id"]
        results = []
        # the clip has a worker without a helmet from ~7 s; send ~4 s of it, one frame at a time
        for i, jpg in enumerate(jpeg_frames(DEMO_CLIP, start_s=6.5, seconds=3.5), start=1):
            ws.send_bytes(jpg)
            msg = ws.receive_json()
            assert msg["type"] == "frame" and msg["frame_id"] == i
            results.append(msg)
        assert results[0]["width"] == 640 and results[0]["height"] == 360
        assert all({"summary", "workers", "unverified", "events", "latency_ms"} <= set(r) for r in results)
        assert any(r["summary"]["violations"] + r["summary"]["at_risk"] > 0 for r in results)
        w = next(w for r in results for w in r["workers"])
        assert len(w["box"]) == 4 and isinstance(w["id"], int)
    # after disconnect, any violation opened in this session is stored and closed
    evs = client.get("/api/events", params={"source": "stream", "source_id": sid}).json()
    assert all(e["status"] == "closed" for e in evs)
    started = [e for r in results for e in r["events"] if e["type"] == "violation_started"]
    assert len(evs) == len(started)
    for e in started:
        assert client.get(e["snapshot_url"]).status_code == 200


def test_stream_bad_frame_reports_error_and_continues(client):
    with client.websocket_connect("/api/stream") as ws:
        ws.receive_json()
        ws.send_bytes(b"not a jpeg")
        assert ws.receive_json()["type"] == "error"
        ws.send_bytes(next(jpeg_frames(DEMO_CLIP, seconds=0.1)))
        assert ws.receive_json()["type"] == "frame"


def test_stream_limit(client):
    from app.settings import settings

    conns = [client.websocket_connect("/api/stream") for _ in range(settings.max_streams)]
    opened = [c.__enter__() for c in conns]
    try:
        for ws in opened:
            assert ws.receive_json()["type"] == "ready"
        with client.websocket_connect("/api/stream") as extra:
            msg = extra.receive_json()
            assert msg["type"] == "error" and "busy" in msg["message"]
    finally:
        for c in conns:
            c.__exit__(None, None, None)
