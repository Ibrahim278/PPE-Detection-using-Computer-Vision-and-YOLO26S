"""PPE compliance API.

    uvicorn app.main:app --reload          (from api/)
    OpenAPI docs: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import detect, events, jobs, meta, stream
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Load models and run one dummy inference so the first real request is fast.
    import numpy as np
    from fastapi.concurrency import run_in_threadpool

    from app.runtime import image_detector
    await run_in_threadpool(image_detector.detect, np.zeros((640, 640, 3), np.uint8))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PPE Compliance API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(meta.router, prefix="/api")
    app.include_router(detect.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    # Annotated videos and snapshots (StaticFiles handles Range requests and blocks path traversal)
    app.mount("/media", StaticFiles(directory=settings.storage_dir), name="media")
    return app


app = create_app()
