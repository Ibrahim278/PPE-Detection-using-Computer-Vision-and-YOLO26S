"""Evaluate weights on a split and tune per-class confidence thresholds.

    python -m ppe.evaluate --weights runs/detect/ppe_yolo26s_v3/weights/best.pt \
        --data data/ppe2/data.yaml --split test --out outputs/eval_v3

Writes ``metrics.json`` (overall + per class) and ``thresholds.json`` (the
confidence that maximises F1 for each class, read off the F1-confidence curve).
Use ``--classes 0 1`` to score an older 3-class model (v2) on the 2-class data,
so v2 and v3 are compared on exactly the same test images.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ppe.config import get_device, resolve


def best_f1_thresholds(box, names: dict[int, str]) -> dict[str, dict[str, float]]:
    """Per class: the confidence with the highest F1, and that F1."""
    out = {}
    px = np.asarray(box.px)
    for row, cls in enumerate(box.ap_class_index):
        f1 = np.asarray(box.f1_curve[row])
        i = int(f1.argmax())
        out[names[int(cls)]] = {"conf": round(float(px[i]), 3), "f1": round(float(f1[i]), 4)}
    return out


def summarize(metrics, names: dict[int, str]) -> dict:
    box = metrics.box
    per_class = {}
    for row, cls in enumerate(box.ap_class_index):
        p, r, ap50, ap = box.class_result(row)
        per_class[names[int(cls)]] = {
            "precision": round(float(p), 4), "recall": round(float(r), 4),
            "mAP50": round(float(ap50), 4), "mAP50-95": round(float(ap), 4),
        }
    return {
        "mAP50": round(float(box.map50), 4), "mAP50-95": round(float(box.map), 4),
        "precision": round(float(box.mp), 4), "recall": round(float(box.mr), 4),
        "per_class": per_class,
        "speed_ms": {k: round(float(v), 2) for k, v in metrics.speed.items()},
    }


def evaluate(weights: str, data: str, split: str = "test", out: str | None = None,
             classes: list[int] | None = None, imgsz: int = 640, device: str | None = None) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(resolve(weights)))
    out_dir = resolve(out) if out else resolve(weights).parent.parent / f"eval_{split}"
    # Low conf (Ultralytics default 0.001) so the PR / F1 curves cover the full range.
    metrics = model.val(data=str(resolve(data)), split=split, imgsz=imgsz, classes=classes,
                        device=get_device(device), plots=True, project=str(out_dir.parent),
                        name=out_dir.name, exist_ok=True, verbose=False)
    names = model.names
    result = {"weights": str(resolve(weights)), "data": str(resolve(data)), "split": split,
              **summarize(metrics, names)}
    thresholds = best_f1_thresholds(metrics.box, names)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2))
    (out_dir / "thresholds.json").write_text(json.dumps(thresholds, indent=2))
    print(json.dumps(result, indent=2))
    print("Best-F1 thresholds:", json.dumps(thresholds))
    print(f"Saved to {out_dir}")
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", default="data/ppe2/data.yaml")
    ap.add_argument("--split", default="test")
    ap.add_argument("--out")
    ap.add_argument("--classes", type=int, nargs="*", help="only score these class ids")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device")
    a = ap.parse_args(argv)
    evaluate(a.weights, a.data, a.split, a.out, a.classes, a.imgsz, a.device)


if __name__ == "__main__":
    main()
