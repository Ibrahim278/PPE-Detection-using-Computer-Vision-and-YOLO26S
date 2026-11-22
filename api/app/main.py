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
from app.routers import meta
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PPE Compliance API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(meta.router, prefix="/api")
    # Annotated videos and snapshots (StaticFiles handles Range requests and blocks path traversal)
    app.mount("/media", StaticFiles(directory=settings.storage_dir), name="media")
    return app


app = create_app()
