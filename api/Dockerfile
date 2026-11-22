# PPE compliance API (CPU). Build from the repo root:
#   docker build -f api/Dockerfile -t siteguard-api .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PPE_STORAGE_DIR=/data \
    PPE_DEVICE=cpu \
    PPE_PERSON_MODEL=yolo26n.pt

# ffmpeg: H.264 output, probing/trimming, yt-dlp sections. libgl/glib: OpenCV runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Heavy, rarely-changing dependencies first (cached between code changes).
RUN pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
COPY api/requirements.docker.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# 2) The model files the API serves (keep repo-relative paths; configs reference them).
COPY ["Training and Validation/ppe_yolo26s_v3/weights/best.pt", "/app/Training and Validation/ppe_yolo26s_v3/weights/best.pt"]
COPY ["Evaluation and Testing/v3/metrics/", "/app/Evaluation and Testing/v3/metrics/"]

# 3) Code. Editable installs keep ppe's config paths relative to /app/ml.
COPY ml/pyproject.toml /app/ml/pyproject.toml
COPY ml/ppe /app/ml/ppe
COPY ml/configs /app/ml/configs
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/app /app/api/app
RUN pip install --no-deps -e /app/ml -e /app/api

# 4) Bake in the COCO person model so the container never downloads at startup.
#    Nano on CPU: person boxes only feed the "head not visible" count, and it halves the cost (61 -> 29 ms).
RUN cd /app/ml && python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')" && test -f /app/ml/yolo26n.pt

RUN useradd --create-home --uid 10001 app && mkdir -p /data /tmp/ultralytics && chown -R app:app /data /tmp/ultralytics
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# One worker: jobs run on an in-process queue and live streams are limited per process.
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
