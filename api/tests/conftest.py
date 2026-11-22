import os
import tempfile
from pathlib import Path

import pytest

# Isolated storage + DB for every test session (must be set before app import).
os.environ.setdefault("PPE_STORAGE_DIR", tempfile.mkdtemp(prefix="ppe-api-test-"))

REPO = Path(__file__).resolve().parents[2]
DEMO_CLIP = REPO / "Project Demo Videos/clip_v1_s2/clip_v1_s2.avi"   # has a real no-helmet worker at ~7-10 s
SAMPLE_IMAGE = REPO / "Evaluation and Testing/v3/violation_snapshots/clip_v1_s2_event1.jpg"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def wait_for_job(client, job_id, timeout=180):
    import time

    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.5)
    raise TimeoutError(job_id)
