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

## Results: v2 vs v3 on the same test set (502 images, helmet + head)

Both models are scored on the identical, unseen test split
(`ppe.evaluate`, PyTorch, default rectangular batches).

| Model | mAP@50 | mAP@50-95 | Precision | Recall | helmet mAP@50-95 | head mAP@50-95 | head P / R | best-F1 conf (helmet / head) |
|---|---|---|---|---|---|---|---|---|
| v2 | 0.963 | 0.635 | 0.942 | 0.918 | 0.639 | 0.632 | 0.935 / 0.901 | 0.53 / 0.42 |
| **v3** | **0.963** | **0.639** | 0.932 | **0.926** | **0.644** | **0.635** | 0.915 / **0.908** | 0.39 / 0.45 |

**Accuracy is effectively a tie.** v3 has slightly tighter boxes and higher recall,
and slightly lower bare-head precision; with 574 head boxes, gaps under ~0.01
are within noise. v2's headline 0.64 mAP@50 came from averaging in the
broken `person` class (0.008). The Phase 1 gains are in the system:

* a clean 2-class model (no junk `person` boxes), with people from a COCO model;
* tracking + smoothing + events: on the demo clips v3 tracked more workers in every
  clip (e.g. peak 12 → 13, 8 → 12) and flagged a real no-helmet road worker in
  `clip_v1_s2` that the v2 output labelled but never turned into an alert
  (see `Evaluation and Testing/v3/`);
* tuned per-class thresholds, browser-playable MP4 output, ONNX export.

Training: 100 epochs, 8.0 h on an Apple M5 (MPS, batch 16); best epoch 86.
Artifacts: `Training and Validation/ppe_yolo26s_v3/` (weights, curves, config) and
`Evaluation and Testing/v3/` (metrics, thresholds, demo videos, snapshots).

### ONNX export

`best.onnx` (38 MB) scores 0.963 / 0.619 on the test set. That equals the
PyTorch model evaluated the same way (square 640 input, batch 1: 0.963 / 0.619),
so the export is exact; the gap to 0.639 is from square padding versus
rectangular batches, not from the conversion.

## Speed (Apple M5)

| Weights | Backend | median ms | FPS |
|---|---|---|---|
| v3 `best.pt` | MPS | 11.3 | 89 |
| v3 `best.pt` | CPU (PyTorch) | 34.1 | 29 |
| v3 `best.onnx` | CPU (onnxruntime) | 37.7 | 27 |
| Full monitor (PPE + person + tracking), 640×360 clips | MPS | 27–31 | 32–37 |
