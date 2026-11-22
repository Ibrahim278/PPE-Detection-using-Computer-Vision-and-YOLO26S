import time

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.runtime import image_detector
from app.settings import settings

router = APIRouter(prefix="/detect", tags=["detect"])

MAX_PIXELS = 40_000_000  # ~40 MP; larger images are rejected before inference


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(415, "Not a supported image (use JPEG, PNG, WebP or BMP).")
    if img.shape[0] * img.shape[1] > MAX_PIXELS:
        raise HTTPException(413, "Image has too many pixels.")
    return img


@router.post("/image")
async def detect_image(file: UploadFile = File(...)) -> dict:
    """Detect helmets / bare heads / people in one image.

    Returns boxes in original-image pixels so the frontend can draw them over
    the image it already has. A bare head is reported as a violation directly
    (no temporal smoothing for single images).
    """
    limit = int(settings.max_image_mb * 1024 * 1024)
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Image larger than {settings.max_image_mb:g} MB.")
    img = decode_image(data)
    t0 = time.perf_counter()
    result = await run_in_threadpool(image_detector.detect, img)
    ms = (time.perf_counter() - t0) * 1000
    out = result.to_json()
    out.pop("t", None)
    out.pop("events", None)
    return {"filename": file.filename, "width": img.shape[1], "height": img.shape[0],
            "inference_ms": round(ms, 1), **out}
