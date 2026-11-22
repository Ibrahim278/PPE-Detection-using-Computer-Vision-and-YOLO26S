# `api/`: PPE compliance backend (Phase 2)

FastAPI service around the `ppe` package in [`../ml`](../ml/README.md). It covers
single images, video jobs (upload or URL) and live webcam/stream monitoring, and
stores violation events in SQLite. The React frontend (Phase 3) talks to it.

## Run

```bash
# from the repo root
python -m venv .venv && source .venv/bin/activate      # or: uv venv
pip install -e ml -e "api[platforms,dev]"
cd api && uvicorn app.main:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>. The models load and warm up at
startup (a few seconds). They run on Apple MPS or CUDA if available, otherwise CPU.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/model` | classes, tuned thresholds, smoothing settings, v3 test metrics, v2 baseline, benchmark |
| POST | `/api/detect/image` | multipart `file`. Returns workers (box, status, conf), unverified people, counts |
| POST | `/api/jobs` | multipart `file` **or** form `url`, plus optional `start`/`end` (`225`, `3:45`, `1:20:45`). Returns 202 + job |
| GET | `/api/jobs` | recent jobs |
| GET | `/api/jobs/{id}` | status, `progress` 0–1, `summary`, `video_url`, events with `snapshot_url` |
| GET | `/api/jobs/{id}/timeline` | per-frame counts for charts (downsampled) |
| POST | `/api/jobs/{id}/cancel` | stop a running job |
| DELETE | `/api/jobs/{id}` | delete a finished job, its files and events |
| GET | `/api/events` | violation events (filters: `source`, `source_id`, `status`, `since`, `limit`, `offset`) |
| GET | `/api/events/summary` | totals for the dashboard: total, open, last 24 h, by source, average duration |
| WS | `/api/stream?source=<name>` | live monitoring (see below) |
| GET | `/media/...` | annotated MP4s and snapshots (supports Range for seeking) |

Job status: `queued → downloading → processing → done`, or `failed`
(with a readable `error`) or `cancelled`. One job runs at a time, so jobs never
compete for the GPU. Uploaded and downloaded inputs are deleted after
processing; the annotated video, events and snapshots are kept.

### Video URLs
- **Direct links** (`https://…/clip.mp4`) are fetched with SSRF protection:
  http/https on ports 80/443 only, no credentials in the URL, hosts must resolve
  to public IPs only (blocks localhost, private ranges, link-local/cloud metadata,
  CGNAT, IPv4-mapped tricks), the connection is pinned to the validated IP (TLS is
  still verified against the hostname), redirects are re-checked, and size is capped.
- **YouTube / Vimeo** links go through `yt-dlp` (optional extra), capped at 720p,
  and only the requested `start`–`end` section is downloaded. Check the platform's
  terms before using this beyond personal or academic demos;
  `PPE_ENABLE_PLATFORM_URLS=false` turns it off.

### Live stream protocol (`/api/stream`)
```
server → {"type":"ready","session_id":"…","thresholds":{…},"smoothing":{…}}
client → <binary JPEG/WebP frame>                   (the n-th frame sent has frame_id n)
server → {"type":"frame","frame_id":n,"width":…,"height":…,"summary":{workers,compliant,at_risk,violations,unverified},
          "workers":[{"id","status","box","conf","violation_s","person_box"}],"unverified":[…],
          "events":[{"type":"violation_started"|"violation_ended",…,"snapshot_url"}],"latency_ms":…,"dropped":…}
server → {"type":"error","message":"…"}             (bad frame; stream continues)
```
- The server always processes the newest frame and drops the rest, so delay doesn't build up.
  Draw the boxes for `frame_id` on a `<canvas>` over your own `<video>`.
- Send frames at the camera's size (640–1280 px wide) as **JPEG quality ≈ 0.92 or
  WebP ≈ 0.9**. Heavier compression can hide borderline bare heads.
- At most `PPE_MAX_STREAMS` streams at once. Extra connections get an error and close code 1013.
- Measured on an Apple M5 against a real uvicorn server at 30 FPS: about 33 ms median per frame.

## Configuration (environment variables)

| Variable | Default | |
|---|---|---|
| `PPE_STORAGE_DIR` | `api/storage` | job outputs, snapshots, SQLite DB |
| `PPE_DB_URL` | `sqlite:///<storage>/ppe.db` | any SQLAlchemy URL |
| `PPE_MONITOR_CONFIG` | `ml/configs/monitor.yaml` | model, thresholds, smoothing |
| `PPE_DEVICE` | `auto` | `mps`, `cpu`, `0` (CUDA) |
| `PPE_PERSON_MODEL` | from `monitor.yaml` (`yolo26s.pt`) | e.g. `yolo26n.pt` (about 2× faster on CPU; the Docker image's default) or `none` |
| `PPE_CPU_THREADS` | all available cores | CPU inference threads (Ultralytics would otherwise force 1) |
| `PPE_CORS_ORIGINS` | `http://localhost:5173,…` | comma-separated frontend origins |
| `PPE_CORS_ORIGIN_REGEX` | – | extra origins as a regex, e.g. Vercel previews `https://siteguard(-[a-z0-9-]+)?\.vercel\.app` |
| `PPE_MAX_IMAGE_MB` / `PPE_MAX_UPLOAD_MB` | 15 / 500 | |
| `PPE_MAX_VIDEO_SECONDS` | 600 | longer videos need a `start`/`end` section |
| `PPE_MAX_STREAMS` | 2 | concurrent live streams |
| `PPE_ENABLE_PLATFORM_URLS` | `true` | YouTube/Vimeo via yt-dlp |
| `PPE_ALLOW_PRIVATE_URLS` | `false` | only for a LAN camera in local testing; never on a public server |

## Tests

```bash
pytest api/tests                          # 39 tests (the network one is skipped): endpoints, jobs, stream, URL safety
PPE_TEST_NETWORK=1 pytest api/tests       # also downloads a demo clip from this repo on GitHub
```
