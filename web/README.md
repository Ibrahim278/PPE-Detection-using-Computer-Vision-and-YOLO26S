# `web/`: SiteGuard frontend (Phase 3)

React 18 + TypeScript + Vite + Tailwind v4 app for the [`api/`](../api/README.md) backend.

| Page | What it does |
|---|---|
| **Live Monitor** (`/`) | Webcam, or a video file played as a camera. Boxes are drawn on a canvas over the video, with a live counter (workers / compliant / violations / compliance %) and a violation feed with snapshots. |
| **Analyze** (`/analyze`) | Image: instant result with boxes. Video file or link (YouTube, Vimeo, direct MP4), with an optional start/end section: runs as a background job. Recent videos list. |
| **Job result** (`/jobs/:id`) | Live progress, then the annotated video, a workers-over-time chart with violation bands, and the violation list (click one to jump the video there). Cancel / delete. |
| **Violations** (`/violations`) | Totals, filters (source, status), incidents-per-hour/day chart, every incident with a snapshot, CSV export. |
| **Model** (`/model`) | v3 test metrics vs v2, per-class results and thresholds, how alerts work, speed. |

## Run (development)

```bash
# terminal 1: API on :8000 (see api/README.md)
cd api && uvicorn app.main:app --port 8000
# terminal 2: frontend on :5173 (proxies /api and /media to :8000)
cd web && npm install && npm run dev
```

Open <http://localhost:5173>. The webcam needs `localhost` or HTTPS (browser rule).

## Build

```bash
npm run build        # type-checks, then outputs static files to dist/
```

Set `VITE_API_URL=https://api.example.com` at build time when the API is on another origin
(then add the frontend's origin to the API's `PPE_CORS_ORIGINS`).

## Notes
- **Live frame rate matters.** The tracker follows heads by box overlap between frames, so it
  needs about 10+ FPS. The client keeps two frames in flight (up to 20 FPS) and shows a warning
  below 10 FPS. Browsers slow down background tabs, so keep the monitor tab visible.
- Frames are sent as JPEG quality 0.92, scaled to at most 1280 px wide.
- Dependencies are pinned exactly; `npm audit` reports 0 vulnerabilities.
