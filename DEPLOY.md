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

## Frontend on Vercel + API on a container host

Vercel is a good fit for the **web app** (a static Vite build), but it **can't run the API**: Python
functions there are capped at about 250 MB (PyTorch alone is over 600 MB), can't run background video
jobs, have no persistent disk for the database and videos, and don't support the WebSocket that Live
Monitor uses. So deploy the API container somewhere that runs Docker, and point the Vercel app at it.

**1. Deploy the API.** The recommended path is Render (next section). Any other Docker host with HTTPS works too
(`api/Dockerfile`, build context = repo root):
Render, Railway, Fly.io, Google Cloud Run (min instances 1, since jobs run in the background), AWS, or a
VPS. Give it a persistent volume at `/data`, 2+ GB RAM, and set:

```
PPE_CORS_ORIGINS=https://<your-project>.vercel.app
PPE_CORS_ORIGIN_REGEX=https://<your-project>(-[a-z0-9-]+)?\.vercel\.app   # optional: preview deployments
```

The build needs the model weights, which are in Git LFS: make sure the host fetches LFS files
(or run `git lfs pull --include="Training and Validation/ppe_yolo26s_v3/weights/best.pt"` before
building). Check it works: `https://<api-host>/api/health` returns `{"status":"ok"}`.

**2. Deploy the web app on Vercel**
1. *Add New → Project*, import this GitHub repository.
2. **Root Directory:** `web` (Vercel then picks up `web/vercel.json`: Vite, `npm ci`, `dist/`, SPA routing).
3. **Environment variable:** `VITE_API_URL=https://<api-host>` (no trailing slash). It's baked in at
   build time, so redeploy after changing it.
4. Leave *Git LFS* off in the Vercel project settings: the web build doesn't need the LFS files,
   and fetching them would use up your LFS bandwidth.
5. Deploy. The browser then calls the API directly: HTTPS for requests and media, WSS for Live Monitor.

**Checks after deploying:** open the Model page (it shows metrics if the API is reachable and CORS
is right); in Analyze, upload a short video; on Live Monitor, allow the camera (Vercel serves HTTPS,
so the webcam works).

**Common problems**
- *"Can't reach the API server"* or CORS errors: the Vercel URL isn't in `PPE_CORS_ORIGINS`/`PPE_CORS_ORIGIN_REGEX`,
  or `VITE_API_URL` is wrong (check for a trailing slash, or `http://` instead of `https://`).
- *Live Monitor won't connect:* the API host must allow WebSockets on `/api/stream` (most do; some
  free tiers or proxies don't).
- *Jobs vanish or stop:* the API host scaled to zero or restarted. Keep one instance always on.

## API on Render (recommended)

CI builds the API image on every push to `main` (with the model weights from Git LFS), smoke-tests it, and
publishes it to GitHub Container Registry as `ghcr.io/ibrahim278/siteguard-api` (`:latest` and `:sha-<commit>`).
Render runs that image, so it never needs Git LFS or has to build PyTorch itself.

**Cost:** the `standard` plan (1 CPU, 2 GB RAM, about $25/month) plus a 5 GB disk (about $1.25/month). The free and
starter plans have 512 MB of RAM, less than the API uses at idle. Billing is per second while running, so you can
*Suspend* the service in the dashboard between demos. Check current prices at render.com/pricing.

**One-time setup**

1. **Publish the first image:** push to `main` (or re-run the CI workflow) and wait for the *Docker images* job to pass.
2. **Let Render pull it:** on GitHub, go to your profile → *Packages* → `siteguard-api` → *Package settings* →
   *Change visibility* → **Public**. (To keep it private instead, create a GitHub token with `read:packages`, add it in
   Render under *Workspace Settings → Container Registry Credentials* as `ghcr`, and uncomment `creds` in `render.yaml`.)
3. **Create the service:** in Render, *New → Blueprint*, pick this repository; it reads `render.yaml`.
   When asked, enter:
   - `PPE_CORS_ORIGINS`: your Vercel URL, e.g. `https://siteguard.vercel.app`
   - `PPE_CORS_ORIGIN_REGEX`: optional, for Vercel preview URLs, e.g. `https://siteguard(-[a-z0-9-]+)?\.vercel\.app`
4. **Wait for the first deploy** (pulling the ~1 GB image takes a few minutes), then open
   `https://<service>.onrender.com/api/health`. It should return `{"status":"ok"}`.
5. **Auto-deploy on every push:** in the Render service, *Settings → Deploy Hook*, copy the URL. On GitHub:
   *Settings → Secrets and variables → Actions → New repository secret*, name `RENDER_DEPLOY_HOOK_URL`, paste the URL.
   From then on, each green CI run on `main` deploys that exact image (`:sha-<commit>`) to Render.
6. **Connect Vercel:** set `VITE_API_URL=https://<service>.onrender.com` in the Vercel project and redeploy it.

**What to expect on 1 CPU:** image and video analysis work, but slower than the numbers above (roughly a few frames
per second for video jobs). Live Monitor will be too slow for reliable tracking (it needs about 10 FPS), so use it
locally or upgrade the plan. `render.yaml` sets `PPE_CPU_THREADS=1` and `PPE_MAX_STREAMS=1` to match the plan;
raise them if you pick a bigger one.

**Notes**
- The container's entrypoint uses Render's `$PORT`, makes the mounted disk writable for the unprivileged `app` user,
  then drops root privileges.
- A service with a disk restarts with a short gap during deploys (no zero-downtime deploys), and running jobs are
  marked failed on restart.
- If a build fails with "best.pt is a Git LFS pointer", the weights weren't downloaded before building
  (`git lfs pull --include="Training and Validation/ppe_yolo26s_v3/weights/best.pt"`).

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
