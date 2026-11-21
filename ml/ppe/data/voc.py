"""Pascal VOC parsing and conversion to YOLO labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree


@dataclass
class Box:
    name: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass
class Annotation:
    filename: str
    width: int
    height: int
    objects: list[Box] = field(default_factory=list)


def parse_voc(xml_path: str | Path) -> Annotation:
    root = etree.parse(str(xml_path)).getroot()
    size = root.find("size")
    ann = Annotation(
        filename=root.findtext("filename"),
        width=int(size.findtext("width")),
        height=int(size.findtext("height")),
    )
    for obj in root.findall("object"):
        bb = obj.find("bndbox")
        ann.objects.append(
            Box(
                name=obj.findtext("name").strip().lower(),
                xmin=float(bb.findtext("xmin")),
                ymin=float(bb.findtext("ymin")),
                xmax=float(bb.findtext("xmax")),
                ymax=float(bb.findtext("ymax")),
            )
        )
    return ann


def to_yolo_lines(ann: Annotation, class_ids: dict[str, int]) -> list[str]:
    """Convert to YOLO ``cls cx cy w h`` lines (normalised).

    Objects whose class is not in ``class_ids`` are dropped. Boxes are clipped to
    the image and degenerate boxes are skipped.
    """
    lines = []
    W, H = ann.width, ann.height
    for b in ann.objects:
        if b.name not in class_ids:
            continue
        x1, x2 = max(0.0, min(b.xmin, b.xmax)), min(float(W), max(b.xmin, b.xmax))
        y1, y2 = max(0.0, min(b.ymin, b.ymax)), min(float(H), max(b.ymin, b.ymax))
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue
        cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
        w, h = (x2 - x1) / W, (y2 - y1) / H
        lines.append(f"{class_ids[b.name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return lines
