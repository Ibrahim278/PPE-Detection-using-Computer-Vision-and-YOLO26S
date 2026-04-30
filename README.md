

- [Overview](#overview)
- [Demo](#demo)
- [Dataset](#dataset)
- [Model & Architecture](#model--architecture)
- [Results](#results)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Training](#training)
- [Evaluation](#evaluation)
- [Inference on Video](#inference-on-video)
- [Technologies Used](#technologies-used)

---

# PPE Detection with YOLO26S

Workplace safety is a critical concern across industries, and construction sites in particular present a high risk of head injuries. Regulatory bodies worldwide mandate the use of hard hats on active sites, yet enforcing compliance manually is labour-intensive, inconsistent, and impractical at scale. This project addresses that challenge by building an automated **Personal Protective Equipment (PPE) detection system** powered by deep learning.

The system fine-tunes a pretrained **YOLO26S** (You Only Look Once) object detection model on a dataset of 5,000 real-world construction site images, training it to distinguish between workers wearing hard hats, workers with bare heads, and general person detections in a single forward pass. Once deployed, the model can process live video feeds or recorded footage in real time, flagging non-compliant workers instantly — enabling site supervisors to act on safety violations as they happen rather than after the fact.

Beyond the immediate safety application, this project demonstrates a complete, end-to-end computer vision pipeline: raw data acquisition and annotation parsing, class imbalance handling through targeted oversampling, annotation format conversion from Pascal VOC XML to YOLO-compatible labels, model fine-tuning with aggressive data augmentation, rigorous per-class evaluation, and finally video inference on real construction footage sourced from YouTube. The entire workflow runs from a single self-contained Jupyter notebook, making it straightforward to reproduce, extend, or adapt to other PPE categories such as high-visibility vests or safety goggles.

---

## Table of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Dataset](#dataset)
- [Model & Architecture](#model--architecture)
- [Results](#results)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Training](#training)
- [Evaluation](#evaluation)
- [Inference on Video](#inference-on-video)
- [Technologies Used](#technologies-used)

---

## Overview

This project fine-tunes a pretrained **YOLO26S** object detection model on the [Safety Helmet Detection dataset](https://www.kaggle.com/datasets/andrewmvd/hard-hat-detection) from Kaggle to identify:

| Class    | Description                        | Color  |
|----------|------------------------------------|--------|
| `helmet` | Worker wearing a hard hat (safe)   | Green  |
| `head`   | Bare head — no hard hat (unsafe)   | Red    |
| `person` | Person body                        | Orange |

The model is trained and evaluated in **Google Colab** with GPU acceleration, and inference is demonstrated on real-world construction site videos sourced from YouTube. The entire workflow is reproducible from a single notebook — no manual data wrangling required.

---

## Demo

Sample detection outputs are available in `Evaluation and Testing/sample_detections/`. Project demo videos (`.avi`) are in `Project Demo Videos/`.

---

## Dataset

- **Source:** [Kaggle — Safety Helmet Detection](https://www.kaggle.com/datasets/andrewmvd/hard-hat-detection)
- **Format:** Pascal VOC XML annotations
- **Size:** 5,000 images / 5,000 annotation files
- **Image dimensions:** ~416×416 px

### Class Distribution

| Class    | Instances | Percentage |
|----------|-----------|------------|
| `helmet` | 18,966    | 74.4%      |
| `head`   | 5,785     | 22.7%      |
| `person` | 751       | 2.9%       |
| **Total**| **25,502**|            |

> **Note:** The `person` class is heavily underrepresented. Oversampling (`PERSON_OVERSAMPLE = 5`) is applied during preprocessing to address this imbalance.

The dataset is split into **train / val / test** sets and converted from Pascal VOC XML to **YOLO label format** (normalized bounding box coordinates).

---

## Model & Architecture

- **Base model:** `yolo26s.pt` (pretrained YOLO26S)
- **Task:** Object detection
- **Input size:** 640×640
- **Framework:** [Ultralytics](https://github.com/ultralytics/ultralytics) (v8.4.35)

---

## Results

Evaluated on the held-out **test set** with a confidence threshold of `0.4`:

| Metric        | Overall | `helmet` | `head`  | `person` |
|---------------|---------|----------|---------|----------|
| **mAP@50**    | 0.6426  | 0.9700   | 0.9495  | 0.0084   |
| **mAP@50-95** | 0.4335  | 0.6522   | 0.6436  | 0.0046   |
| **Precision** | 0.6254  | 0.9427   | 0.9336  | 0.0000   |
| **Recall**    | 0.6041  | 0.9273   | 0.8850  | 0.0000   |

> The `helmet` and `head` classes achieve strong performance (mAP@50 > 0.94). The `person` class performs poorly due to extreme class imbalance in the dataset.

Training curves, confusion matrices, and PR curves are saved in `Training and Validation/ppe_yolo26s_v2/`.

---

## Project Structure

```
PPE Detection with YOLO26S/
│
├── Config Files/
│   ├── training_config.json       # Training hyperparameters
│   └── val_config.json            # Validation/test configuration
│
├── Evaluation and Testing/
│   ├── metrics/
│   │   ├── class_distribution.png
│   │   ├── confusion_matrix.png
│   │   ├── confusion_matrix_normalized.png
│   │   └── test_results.txt       # mAP, precision, recall per class
│   └── sample_detections/
│       ├── failures/              # Hard failure cases
│       └── det_*.png              # Successful detection examples
│
├── Training and Validation/
│   ├── ppe_yolo26s_v2/
│   │   ├── weights/
│   │   │   ├── best.pt            # Best checkpoint
│   │   │   └── last.pt            # Final checkpoint
│   │   ├── results.csv            # Per-epoch metrics
│   │   ├── results.png
│   │   ├── args.yaml              # Full training config (auto-generated)
│   │   └── *.png                  # Training curves & batch previews
│   └── val/                       # Validation run outputs
│
├── Project Demo Videos/
│   └── clip_v*/                   # Annotated video clips (.avi)
│
├── PPE_Detection_Project_Code.ipynb   # Main notebook (Colab)
├── Project Report.docx
├── Project Presentation.pptx
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.8+
- A GPU (CUDA or Apple MPS) is strongly recommended
- A Kaggle account (for dataset download)

### Installation

```bash
pip install ultralytics opencv-python-headless matplotlib seaborn pandas numpy scikit-learn lxml pyyaml tqdm
```

### Running in Google Colab (Recommended)

1. Upload `PPE_Detection_Project_Code.ipynb` to Google Colab.
2. Mount Google Drive when prompted.
3. Run all cells sequentially — the notebook handles dataset download, preprocessing, training, evaluation, and inference automatically.

### Running Locally

1. Clone or download this repository.
2. Install dependencies (see above).
3. Open `PPE_Detection_Project_Code.ipynb` in Jupyter.
4. Set `PROJECT_ROOT` to your local project directory.
5. Run all cells.

---

## Configuration

### Training (`Config Files/training_config.json`)

| Parameter        | Value          | Description                          |
|------------------|----------------|--------------------------------------|
| `model`          | `yolo26s.pt`   | Pretrained base model                |
| `epochs`         | 100            | Max training epochs                  |
| `batch`          | 16             | Batch size                           |
| `imgsz`          | 640            | Input image size                     |
| `patience`       | 20             | Early stopping patience              |
| `lr0`            | 0.01           | Initial learning rate                |
| `lrf`            | 0.01           | Final learning rate factor           |
| `copy_paste`     | 0.5            | Copy-paste augmentation probability  |
| `mixup`          | 0.15           | Mixup augmentation probability       |
| `optimizer`      | `auto`         | Optimizer selection                  |
| `device`         | `cuda`         | Compute device                       |

### Evaluation (`Config Files/val_config.json`)

| Parameter        | Value   | Description                    |
|------------------|---------|--------------------------------|
| `split`          | `test`  | Dataset split to evaluate on   |
| `conf_threshold` | 0.4     | Minimum detection confidence   |
| `device`         | `cuda`  | Compute device                 |

---

## Training

The notebook performs the following steps:

1. **Environment setup** — mounts Google Drive, installs packages, creates directory structure.
2. **Dataset download** — fetches the ~1.3 GB Kaggle dataset (skipped if already present).
3. **Dataset exploration** — parses Pascal VOC XML annotations, plots class distribution, visualises sample images.
4. **Preprocessing** — converts annotations to YOLO format, splits data (train/val/test), applies person-class oversampling, generates `data.yaml`.
5. **Training** — fine-tunes YOLO26S with the configuration above; checkpoints saved every 10 epochs.
6. **Evaluation** — runs the best checkpoint on the test set and reports per-class metrics.
7. **Inference** — downloads YouTube video clips and runs detection, saving annotated `.avi` files.

---

## Evaluation

After training, the best model weights are located at:

```
Training and Validation/ppe_yolo26s_v2/weights/best.pt
```

To re-run evaluation:

```python
from ultralytics import YOLO

model = YOLO("Training and Validation/ppe_yolo26s_v2/weights/best.pt")
results = model.val(data="path/to/data.yaml", split="test", conf=0.4)
```

---

## Inference on Video

The notebook downloads short clips from YouTube construction site videos and runs the trained model on each frame. Annotated output videos are saved to `Project Demo Videos/`.

To run inference on a custom video:

```python
from ultralytics import YOLO

model = YOLO("Training and Validation/ppe_yolo26s_v2/weights/best.pt")
model.predict(source="your_video.mp4", conf=0.4, save=True)
```

---

## Technologies Used

| Tool / Library     | Purpose                              |
|--------------------|--------------------------------------|
| Ultralytics YOLO   | Model training, evaluation, inference|
| PyTorch            | Deep learning backend                |
| OpenCV             | Image/video processing               |
| Matplotlib/Seaborn | Visualisation                        |
| lxml               | Pascal VOC XML parsing               |
| Google Colab       | Cloud GPU training environment       |
| Google Drive       | Persistent storage across sessions   |
