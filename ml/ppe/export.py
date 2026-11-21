"""Export weights for deployment.

    python -m ppe.export --weights <best.pt> --formats onnx coreml

ONNX runs anywhere (onnxruntime on CPU/GPU, used by the API in Phase 2);
CoreML uses the Apple Neural Engine on Macs; ``engine`` (TensorRT) needs an
NVIDIA GPU.
"""

from __future__ import annotations

import argparse

from ppe.config import resolve


def export(weights: str, formats: list[str], imgsz: int = 640, half: bool = False) -> list[str]:
    from ultralytics import YOLO

    outs = []
    for fmt in formats:
        model = YOLO(str(resolve(weights)))
        kw = {"simplify": True} if fmt == "onnx" else {}
        if fmt == "coreml":
            kw["nms"] = True
        outs.append(model.export(format=fmt, imgsz=imgsz, half=half, **kw))
        print(f"{fmt}: {outs[-1]}")
    return outs


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--formats", nargs="+", default=["onnx"], help="onnx coreml engine openvino ...")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--half", action="store_true")
    a = ap.parse_args(argv)
    export(a.weights, a.formats, a.imgsz, a.half)


if __name__ == "__main__":
    main()
