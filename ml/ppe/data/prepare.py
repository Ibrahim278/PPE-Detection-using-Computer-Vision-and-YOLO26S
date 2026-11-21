"""Download the Kaggle hard-hat dataset and build a 2-class YOLO dataset.

    python -m ppe.data.prepare --config configs/data.yaml

Changes from v2 (notebook):
  * ``person`` is dropped. It had 751 inconsistently labelled boxes and scored
    0.008 mAP@50; a pretrained COCO detector handles people instead.
  * No oversampling (duplicating person images also duplicated helmet/head boxes).
  * Split is stratified on whether an image contains a bare head (the class that
    matters for violations), so every split has the same share of violation images.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

from tqdm import tqdm

from ppe.config import load_config, resolve
from ppe.data.voc import parse_voc, to_yolo_lines


KAGGLE_REF = "andrewmvd/hard-hat-detection"


def download(url: str, raw_dir: Path) -> None:
    """Make sure the raw dataset is extracted into ``raw_dir``.

    Order: already extracted -> zip already in raw_dir -> Kaggle CLI (uses your
    own ~/.kaggle/kaggle.json) -> anonymous URL (Kaggle mostly requires auth now).
    """
    if (raw_dir / "annotations").is_dir() and any((raw_dir / "annotations").iterdir()):
        print(f"Dataset already present in {raw_dir}")
        return
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "hard-hat-detection.zip"
    if not zip_path.exists() and shutil.which("kaggle"):
        print(f"Downloading {KAGGLE_REF} with the Kaggle CLI ...")
        subprocess.run(["kaggle", "datasets", "download", "-d", KAGGLE_REF, "-p", str(raw_dir)], check=True)
    if not zip_path.exists():
        print(f"Downloading {url} ...")
        try:
            with tqdm(unit="B", unit_scale=True) as bar:
                def hook(blocks, bs, total):
                    bar.total = total
                    bar.update(blocks * bs - bar.n)
                urllib.request.urlretrieve(url, zip_path, reporthook=hook)
        except urllib.error.HTTPError as e:
            zip_path.unlink(missing_ok=True)
            raise SystemExit(
                f"Anonymous download failed ({e}). Either:\n"
                f"  pip install kaggle   # then rerun; uses ~/.kaggle/kaggle.json\n"
                f"or download https://www.kaggle.com/datasets/{KAGGLE_REF} in a browser and put the zip at\n"
                f"  {zip_path}"
            ) from None
    print("Extracting ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(raw_dir)


def stratified_split(keys: dict[str, int], ratios: dict[str, float], seed: int) -> dict[str, list[str]]:
    """Split names by group key so each split keeps the same group proportions."""
    groups: dict[int, list[str]] = {}
    for name, g in sorted(keys.items()):
        groups.setdefault(g, []).append(name)
    rng = random.Random(seed)
    out = {s: [] for s in ratios}
    for names in groups.values():
        rng.shuffle(names)
        n = len(names)
        n_train = round(n * ratios["train"])
        n_val = round(n * ratios["val"])
        out["train"] += names[:n_train]
        out["val"] += names[n_train : n_train + n_val]
        out["test"] += names[n_train + n_val :]
    return {s: sorted(v) for s, v in out.items()}


def link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def prepare(cfg: dict) -> Path:
    raw_dir = resolve(cfg["raw_dir"])
    out_dir = resolve(cfg["out_dir"])
    classes: list[str] = cfg["classes"]
    class_ids = {c: i for i, c in enumerate(classes)}

    download(cfg["dataset_url"], raw_dir)
    ann_dir, img_dir = raw_dir / "annotations", raw_dir / "images"

    labels: dict[str, tuple[str, list[str]]] = {}
    dropped = Counter()
    for xml in sorted(ann_dir.glob("*.xml")):
        ann = parse_voc(xml)
        img = img_dir / ann.filename
        if not img.exists():
            dropped["missing_image"] += 1
            continue
        dropped.update(o.name for o in ann.objects if o.name not in class_ids)
        labels[xml.stem] = (ann.filename, to_yolo_lines(ann, class_ids))

    head_id = class_ids.get("head")
    strat = {k: int(any(l.startswith(f"{head_id} ") for l in v[1])) for k, v in labels.items()}
    splits = stratified_split(strat, cfg["split"], cfg["seed"])

    if out_dir.exists():
        shutil.rmtree(out_dir)
    stats = {}
    for split, names in splits.items():
        (out_dir / "images" / split).mkdir(parents=True)
        (out_dir / "labels" / split).mkdir(parents=True)
        counts = Counter()
        for name in tqdm(names, desc=split):
            fname, lines = labels[name]
            link_or_copy(img_dir / fname, out_dir / "images" / split / fname)
            (out_dir / "labels" / split / f"{Path(fname).stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
            counts.update(classes[int(l.split()[0])] for l in lines)
        stats[split] = {"images": len(names), "boxes": dict(counts)}

    (out_dir / "data.yaml").write_text(
        f"path: {out_dir}\ntrain: images/train\nval: images/val\ntest: images/test\n"
        f"nc: {len(classes)}\nnames: {json.dumps(classes)}\n"
    )
    stats["dropped"] = dict(dropped)
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(f"Wrote {out_dir / 'data.yaml'}")
    return out_dir


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args(argv)
    prepare(load_config(args.config))


if __name__ == "__main__":
    main()
