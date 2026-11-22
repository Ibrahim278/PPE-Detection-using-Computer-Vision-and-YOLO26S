import os

import pytest

from conftest import DEMO_CLIP, SAMPLE_IMAGE, wait_for_job


def test_health_and_model(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    m = client.get("/api/model").json()
    assert m["classes"] == ["helmet", "head"]
    assert set(m["thresholds"]) == {"helmet", "head"}
    assert m["test_metrics"]["mAP50"] > 0.9


def test_detect_image_finds_bare_head(client):
    with open(SAMPLE_IMAGE, "rb") as f:
        r = client.post("/api/detect/image", files={"file": ("w.jpg", f, "image/jpeg")})
    assert r.status_code == 200
    j = r.json()
    assert j["summary"]["violations"] >= 1
    w = j["workers"][0]
    assert len(w["box"]) == 4 and w["status"] == "violation"


def test_detect_image_rejects_non_image(client):
    r = client.post("/api/detect/image", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_job_requires_exactly_one_source(client):
    assert client.post("/api/jobs").status_code == 422
    with open(DEMO_CLIP, "rb") as f:
        r = client.post("/api/jobs", files={"file": ("a.avi", f, "video/x-msvideo")},
                        data={"url": "https://example.com/a.mp4"})
    assert r.status_code == 422


def test_job_rejects_bad_type_time_and_private_url(client):
    r = client.post("/api/jobs", files={"file": ("notes.txt", b"x", "text/plain")})
    assert r.status_code == 415
    with open(DEMO_CLIP, "rb") as f:
        r = client.post("/api/jobs", files={"file": ("a.avi", f, "video/x-msvideo")}, data={"start": "5", "end": "2"})
    assert r.status_code == 422
    r = client.post("/api/jobs", data={"url": "http://169.254.169.254/latest/meta-data/"})
    assert r.status_code == 422 and "private" in r.json()["detail"]


def test_upload_job_end_to_end(client):
    with open(DEMO_CLIP, "rb") as f:
        r = client.post("/api/jobs", files={"file": ("clip_v1_s2.avi", f, "video/x-msvideo")})
    assert r.status_code == 202
    job = wait_for_job(client, r.json()["id"])
    assert job["status"] == "done", job["error"]
    assert job["progress"] == 1.0
    assert job["summary"]["frames_processed"] == 300 and job["summary"]["source"] is None

    # the real no-helmet road worker in this clip becomes one stored event with a snapshot
    assert len(job["events"]) >= 1
    ev = job["events"][0]
    assert ev["status"] == "closed" and ev["duration_s"] > 1
    assert client.get(ev["snapshot_url"]).headers["content-type"] == "image/jpeg"

    # browser-playable video with Range support (needed for seeking)
    v = client.get(job["video_url"], headers={"Range": "bytes=0-1023"})
    assert v.status_code == 206 and len(v.content) == 1024
    assert client.get(job["video_url"]).headers["content-type"] == "video/mp4"

    tl = client.get(f"/api/jobs/{job['id']}/timeline").json()
    assert tl and {"t", "workers", "violations"} <= set(tl[0])

    evs = client.get("/api/events", params={"source": "job", "source_id": job["id"]}).json()
    assert len(evs) == len(job["events"])
    assert client.get("/api/events/summary").json()["total"] >= 1

    # input files are removed after processing; outputs stay
    files = {p.name for p in (__import__("app.services.jobs", fromlist=["x"]).job_dir(job["id"])).iterdir()}
    assert "annotated.mp4" in files and not any(n.startswith("input") for n in files)

    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404
    assert client.get("/api/events", params={"source_id": job["id"]}).json() == []


def test_upload_job_with_section(client):
    with open(DEMO_CLIP, "rb") as f:
        r = client.post("/api/jobs", files={"file": ("c.avi", f, "video/x-msvideo")},
                        data={"start": "0:02", "end": "0:05"})
    job = wait_for_job(client, r.json()["id"])
    assert job["status"] == "done", job["error"]
    assert 2.5 <= job["summary"]["input"]["duration"] <= 3.5
    assert job["start_s"] == 2 and job["end_s"] == 5


def test_start_past_end_fails_cleanly(client):
    with open(DEMO_CLIP, "rb") as f:
        r = client.post("/api/jobs", files={"file": ("c.avi", f, "video/x-msvideo")}, data={"start": "99"})
    job = wait_for_job(client, r.json()["id"])
    assert job["status"] == "failed" and "past the end" in job["error"]


def test_not_a_video_fails_cleanly(client):
    r = client.post("/api/jobs", files={"file": ("fake.mp4", b"\x00" * 2048, "video/mp4")})
    job = wait_for_job(client, r.json()["id"])
    assert job["status"] == "failed" and "video" in job["error"].lower()


@pytest.mark.skipif(not os.environ.get("PPE_TEST_NETWORK"), reason="set PPE_TEST_NETWORK=1 to run")
def test_direct_url_job(client):
    # A demo clip from this project's own public GitHub repo (served by Git LFS over HTTPS).
    url = ("https://media.githubusercontent.com/media/Ibrahim278/PPE-Detection-using-Computer-Vision-and-YOLO26S/"
           "main/Project%20Demo%20Videos/clip_v1_s1/clip_v1_s1.avi")
    r = client.post("/api/jobs", data={"url": url})
    assert r.status_code == 202, r.text
    job = wait_for_job(client, r.json()["id"])
    assert job["status"] == "done", job["error"]
    assert job["summary"]["frames_processed"] == 300
