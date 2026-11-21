"""Config loading shared by every CLI.

Configs are YAML files. Relative paths inside them are resolved against the
``ml/`` directory, so the same config works locally, in CI, and on Colab
(override ``paths.root`` or pass absolute paths there).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ML_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = ML_DIR.parent


def resolve(path: str | Path, base: Path = ML_DIR) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def load_config(path: str | Path) -> dict[str, Any]:
    path = resolve(path)
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    cfg["_config_path"] = str(path)
    return cfg


def get_device(preferred: str | None = None) -> str:
    """Return the best device string for Ultralytics: mps > cuda > cpu."""
    if preferred and preferred != "auto":
        return preferred
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
