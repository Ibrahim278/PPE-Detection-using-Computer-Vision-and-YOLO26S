"""Train a PPE detector from a YAML config.

    python -m ppe.train --config configs/train_v3.yaml [--epochs 1 --fraction 0.1]

Resumes automatically if ``<project>/<name>/weights/last.pt`` exists and
``--fresh`` is not given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppe.config import get_device, load_config, resolve


def train(cfg: dict, overrides: dict | None = None, fresh: bool = False) -> Path:
    from ultralytics import YOLO

    project = resolve(cfg.get("project", "runs/detect"))
    name = cfg["name"]
    run_dir = project / name
    last = run_dir / "weights" / "last.pt"

    args = dict(cfg.get("train", {}))
    args.update({k: v for k, v in (overrides or {}).items() if v is not None})
    args["device"] = get_device(args.get("device"))

    if last.exists() and not fresh:
        print(f"Resuming from {last}")
        YOLO(str(last)).train(resume=True)
    else:
        model = YOLO(cfg["model"])
        model.train(data=str(resolve(cfg["data"])), project=str(project), name=name, exist_ok=True, **args)

    (run_dir / "train_config.json").write_text(json.dumps({**cfg, "train": args}, indent=2, default=str))
    best = run_dir / "weights" / "best.pt"
    print(f"Best weights: {best}")
    return best


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/train_v3.yaml")
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--batch", type=int)
    ap.add_argument("--imgsz", type=int)
    ap.add_argument("--fraction", type=float, help="train on a fraction of the data (smoke tests)")
    ap.add_argument("--device")
    ap.add_argument("--name", help="override run name")
    ap.add_argument("--fresh", action="store_true", help="ignore an existing last.pt")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.name:
        cfg["name"] = a.name
    train(cfg, {"epochs": a.epochs, "batch": a.batch, "imgsz": a.imgsz, "fraction": a.fraction, "device": a.device}, a.fresh)


if __name__ == "__main__":
    main()
