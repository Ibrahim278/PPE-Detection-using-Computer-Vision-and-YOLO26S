"""Measure detector latency on this machine.

    python -m ppe.benchmark --weights best.pt best.onnx best.mlpackage --source clip.mp4 --devices mps cpu

Times ``model.predict`` (preprocess + inference + NMS) over real frames after a
warm-up, and writes a Markdown table you can paste into the README.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

import cv2
import numpy as np

from ppe.config import resolve


def load_frames(source: str | None, n: int) -> list[np.ndarray]:
    if not source:
        rng = np.random.default_rng(0)
        return [rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(n)]
    cap = cv2.VideoCapture(str(resolve(source)))
    frames = []
    while len(frames) < n:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        raise SystemExit(f"No frames read from {source}")
    return frames


def bench(weights: str, device: str, frames: list[np.ndarray], imgsz: int, warmup: int = 10) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(resolve(weights)), task="detect")
    kw = {} if str(weights).endswith((".onnx", ".mlpackage")) and device == "mps" else {"device": device}
    for f in frames[:warmup]:
        model.predict(f, imgsz=imgsz, verbose=False, **kw)
    times = []
    for f in frames:
        s = time.perf_counter()
        model.predict(f, imgsz=imgsz, verbose=False, **kw)
        times.append((time.perf_counter() - s) * 1000)
    med = statistics.median(times)
    return {"weights": str(weights).split("/")[-1], "device": device, "imgsz": imgsz,
            "median_ms": round(med, 1), "p95_ms": round(float(np.percentile(times, 95)), 1),
            "fps": round(1000 / med, 1), "frames": len(times)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", nargs="+", required=True)
    ap.add_argument("--devices", nargs="+", default=["mps", "cpu"])
    ap.add_argument("--source", help="video for realistic frames (default: random 720p frames)")
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--out", help="write results JSON here")
    a = ap.parse_args(argv)
    frames = load_frames(a.source, a.frames)
    rows = []
    for w in a.weights:
        for d in a.devices:
            if str(w).endswith((".onnx", ".mlpackage")) and d != a.devices[0]:
                continue  # exported formats pick their own backend; time once
            rows.append(bench(w, d, frames, a.imgsz))
            print(rows[-1])
    print(f"\nMachine: {platform.machine()} {platform.processor() or ''}".rstrip())
    print("| weights | device | imgsz | median ms | p95 ms | FPS |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['weights']} | {r['device']} | {r['imgsz']} | {r['median_ms']} | {r['p95_ms']} | {r['fps']} |")
    if a.out:
        out = resolve(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
