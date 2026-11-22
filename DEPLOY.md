# Deploying SiteGuard

The app is two containers:

| Container | Image | What it does | Port |
|---|---|---|---|
| `api` | `api/Dockerfile` (built from the repo root) | FastAPI + YOLO26 on CPU, ffmpeg, yt-dlp. Stores SQLite, videos and snapshots in `/data` | 8000 (internal) |
| `web` | `web/Dockerfile` | nginx serving the React build and proxying `/api` (incl. WebSocket) and `/media` to the API | 80 |

## Run locally with Docker

```bash
git lfs pull --include="Training and Validation/ppe_yolo26s_v3/weights/best.pt"   # model weights
docker compose up --build
```

Open <http://localhost:8080>. Data persists in the `ppe-data` volume (`docker compose down -v` deletes it).

## Requirements for a server

- **CPU / RAM:** 2–4 vCPU and 2–4 GB RAM is enough for a demo. Measured in Docker on an Apple M5
  (Linux VM, CPU only): video jobs run at about **7 FPS** and one live stream at about **9 FPS**
  (~100 ms per frame). Live tracking works best at 10+ FPS, so CPU hosting suits video analysis and
  demos; for reliable live monitoring of several cameras, use a GPU host (swap the CPU PyTorch install
  line in `api/Dockerfile` for a CUDA build and set `PPE_DEVICE=0`).
- **CPU threads:** the API uses all available cores (`PPE_CPU_THREADS` to limit). Ultralytics would
  otherwise force single-threaded inference.
- **Image size:** the API image is about 2.9 GB uncompressed (CPU PyTorch plus Ultralytics' own
  dependencies); the web image is about 77 MB.
- **Disk:** a persistent volume for `/data` (annotated videos are kept until deleted).
- **HTTPS:** browsers only allow the webcam on HTTPS (or localhost). Put the `web` container behind
  TLS (a platform-provided certificate, Caddy, or a load balancer).
- **One API replica.** The job queue and live-stream limit are in-process, and SQLite is a single file.
  Scaling out would need Postgres (`PPE_DB_URL`) and an external queue.

## Configuration

API environment variables are listed in [`api/README.md`](api/README.md#configuration-environment-variables).
For a public deployment, keep `PPE_ALLOW_PRIVATE_URLS=false` (the default), and consider
`PPE_ENABLE_PLATFORM_URLS=false` (YouTube/Vimeo downloads) depending on the platforms' terms.

The web container reads `API_UPSTREAM` (default `api:8000`) to find the API.

## Security notes

- There is **no login** yet. Anyone who can reach the URL can upload videos, start the camera
  monitor and see snapshots of workers. Keep a deployment private (VPN, an IP allowlist, or a platform's
  access controls) or add authentication before sharing it publicly.
- The API container runs as a non-root user, and the API isn't exposed directly (only through nginx).
- Snapshots show people's faces. Check your organisation's privacy rules before monitoring real sites.

## CI

`.github/workflows/ci.yml` runs on every push and pull request: Python tests (CPU), the web type-check
and build plus `npm audit`, then builds both images and smoke-tests the stack through nginx. To save
GitHub's LFS bandwidth quota it downloads only the two LFS files it needs, and caches them.
