"""Model loading. Each consumer gets its own ComplianceMonitor because
Ultralytics tracking keeps per-model state (one per job / stream connection)."""

from __future__ import annotations

import json
import threading
from functools import lru_cache

from ppe.compliance.pipeline import ComplianceMonitor
from ppe.config import load_config

from app.settings import settings


@lru_cache
def monitor_config() -> dict:
    cfg = load_config(settings.monitor_config)
    if settings.device != "auto":
        cfg["device"] = settings.device
    if settings.person_model:
        cfg["person_model"] = None if settings.person_model.lower() == "none" else settings.person_model
    return cfg


def new_monitor() -> ComplianceMonitor:
    return ComplianceMonitor.from_config(monitor_config())


class ImageDetector:
    """Shared single-image detector (no tracking), serialised with a lock."""

    def __init__(self) -> None:
        self._monitor: ComplianceMonitor | None = None
        self._lock = threading.Lock()

    def get(self) -> ComplianceMonitor:
        with self._lock:
            if self._monitor is None:
                self._monitor = new_monitor()
            return self._monitor

    def detect(self, frame):
        m = self.get()
        with self._lock:
            return m.detect(frame)


image_detector = ImageDetector()


def model_info() -> dict:
    m = image_detector.get()
    info = {
        "ppe_model": str(monitor_config()["ppe_model"]),
        "person_model": monitor_config().get("person_model"),
        "classes": list(m.ppe.names.values()),
        "thresholds": m.conf,
        "device": m.device,
        "imgsz": m.imgsz,
        "smoothing": {k: getattr(m.state, k) for k in ("min_violation_s", "resolve_s", "lost_s", "ema_alpha")},
    }
    for key, fname in [("test_metrics", "test_metrics_v3.json"), ("baseline_v2", "test_metrics_v2_same_split.json"),
                       ("benchmark", "benchmark_m5.json")]:
        p = settings.metrics_dir / fname
        if p.exists():
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                data.pop("weights", None)
                data.pop("data", None)
            info[key] = data
    return info
