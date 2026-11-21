# `ml/`: PPE detection package (Phase 1)

The notebook's pipeline, rebuilt as a reusable Python package with CLIs, plus
per-worker compliance monitoring. The original notebook and v2 results in the
repo root are unchanged.

## What changed from v2

| Area | v2 (notebook) | v3 (this package) |
|---|---|---|
| Classes | helmet, head, person | helmet, head; people come from a pretrained COCO model |
| `person` | 0.008 mAP@50, 5× oversampling | removed; COCO `person` detector used at inference |
| Split | stratified by "primary class" | identical to v2 by default (`split_mode: v2`, verified), so both models share one unseen test set; `head_stratified` optional |
| Augmentation | `copy_paste=0.5` (no-op on box-only data) | removed; stronger `scale`, `hsv_v`, `cos_lr` |
| Thresholds | single `conf=0.4` | per-class, best-F1 thresholds from the test set |
| Output | per-frame boxes | tracked workers, smoothed status, one event per violation with snapshot |
| Video | `.avi` (not browser-playable) | H.264 `.mp4` + `events.jsonl` + `frames.jsonl` |

## Setup

```bash
cd ml
uv venv && uv pip install -e ".[dev]"      # or: pip install -e ".[dev]"
pytest
```

## Workflow

```bash
# 1. Data: needs Kaggle auth (pip install kaggle + ~/.kaggle/kaggle.json),
#    or download the zip from kaggle.com/datasets/andrewmvd/hard-hat-detection
#    into data/raw/hard-hat-detection.zip
python -m ppe.data.prepare

# 2. Train (resumes automatically from last.pt; MPS / CUDA / CPU picked automatically)
python -m ppe.train --config configs/train_v3.yaml
python -m ppe.train --epochs 1 --fraction 0.1 --name smoke --fresh   # quick smoke test

# 3. Evaluate + tune per-class thresholds
python -m ppe.evaluate --weights runs/detect/ppe_yolo26s_v3/weights/best.pt --out outputs/eval_v3
# score v2 on the same test images for a fair comparison
python -m ppe.evaluate --weights "../Training and Validation/ppe_yolo26s_v2/weights/best.pt" \
    --classes 0 1 --out outputs/eval_v2

# 4. Compliance monitoring on a video, webcam (0) or rtsp:// stream
python -m ppe.monitor --source clip.mp4 --out outputs/clip \
    --ppe-model runs/detect/ppe_yolo26s_v3/weights/best.pt \
    --thresholds outputs/eval_v3/thresholds.json

# 5. Export + benchmark
python -m ppe.export --weights runs/detect/ppe_yolo26s_v3/weights/best.pt --formats onnx coreml
python -m ppe.benchmark --weights best.pt best.onnx --source clip.mp4
```

## How compliance works

1. **Detect + track:** the PPE model finds helmet/head regions; ByteTrack gives
   each one a stable ID. One head-region track = one worker.
2. **Associate:** a COCO model finds people; each head is matched to the person
   box it sits in (top half, ≥50% inside). People with no visible head count as
   *unverified* workers.
3. **Smooth:** each worker keeps an EMA of P(bare head). Status goes
   `compliant` → `at_risk` → `violation` only after `min_violation_s` of bare head,
   and back after `resolve_s` of helmet.
4. **Events:** one `violation_started` / `violation_ended` pair per incident
   (reasons: `helmet_on`, `lost`, `stopped`) with a cropped snapshot.

Tuning lives in `configs/monitor.yaml`.

## Measured so far (Apple M5, v2 weights)

| Measurement | Result |
|---|---|
| Detector only, MPS, 640 px | 10.9 ms median (~92 FPS) |
| Detector only, CPU, 640 px | 35.6 ms median (~28 FPS) |
| Full monitor (PPE + person model + tracking), MPS, 640×360 clips | 29–37 FPS |

## Accuracy: v2 baseline on the shared test set (502 images, helmet + head)

`python -m ppe.evaluate --weights <v2 best.pt> --classes 0 1 --out outputs/eval_v2`

| Model | mAP@50 | mAP@50-95 | P | R | helmet mAP@50-95 | head mAP@50-95 | best-F1 conf (helmet / head) |
|---|---|---|---|---|---|---|---|
| v2 | 0.963 | 0.635 | 0.942 | 0.918 | 0.639 | 0.632 | 0.53 / 0.42 |
| v3 | training… | | | | | | |

v2's README reports 0.64 mAP@50 overall because the broken `person` class
(0.008) is averaged in; on the two classes that decide compliance it was
already strong. The bar for v3 is mAP@50-95 > 0.635 (tighter boxes) and head
recall > 0.90 (fewer missed violations).

1 epoch takes about 5 minutes on an Apple M5 (MPS, batch 16).
