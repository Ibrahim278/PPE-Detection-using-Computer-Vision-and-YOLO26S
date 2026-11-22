from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app import runtime

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/model")
async def model() -> dict:
    """Model, thresholds, smoothing settings and test-set metrics (for the Model page)."""
    return await run_in_threadpool(runtime.model_info)
