"""Runtime settings, read from environment variables (prefix ``PPE_``)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = API_DIR.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"PPE_{name}", default)


def _bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    storage_dir: Path = field(default_factory=lambda: Path(_env("STORAGE_DIR", str(API_DIR / "storage"))).resolve())
    db_url: str = field(default_factory=lambda: _env("DB_URL", ""))
    monitor_config: Path = field(default_factory=lambda: Path(_env("MONITOR_CONFIG", str(REPO_DIR / "ml/configs/monitor.yaml"))))
    metrics_dir: Path = field(default_factory=lambda: Path(_env("METRICS_DIR", str(REPO_DIR / "Evaluation and Testing/v3/metrics"))))
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in _env(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()])

    max_image_mb: float = field(default_factory=lambda: float(_env("MAX_IMAGE_MB", "15")))
    max_upload_mb: float = field(default_factory=lambda: float(_env("MAX_UPLOAD_MB", "500")))
    max_video_seconds: float = field(default_factory=lambda: float(_env("MAX_VIDEO_SECONDS", "600")))
    max_streams: int = field(default_factory=lambda: int(_env("MAX_STREAMS", "2")))
    download_timeout_s: float = field(default_factory=lambda: float(_env("DOWNLOAD_TIMEOUT_S", "120")))

    enable_platform_urls: bool = field(default_factory=lambda: _bool("ENABLE_PLATFORM_URLS", True))
    # Only for local testing against your own LAN camera/server. Never enable on a public deployment.
    allow_private_urls: bool = field(default_factory=lambda: _bool("ALLOW_PRIVATE_URLS", False))

    def __post_init__(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_url:
            self.db_url = f"sqlite:///{self.storage_dir / 'ppe.db'}"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_dir / "jobs"

    @property
    def streams_dir(self) -> Path:
        return self.storage_dir / "streams"


settings = Settings()
