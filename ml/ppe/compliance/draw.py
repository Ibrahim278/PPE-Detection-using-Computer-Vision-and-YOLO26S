"""Draw compliance overlays onto BGR frames (used for annotated video output)."""

from __future__ import annotations

import cv2
import numpy as np

COLORS = {  # BGR
    "compliant": (80, 200, 60),
    "at_risk": (0, 170, 255),
    "violation": (40, 40, 230),
    "unverified": (170, 170, 170),
}


def _label(img, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(th + 4, y)
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 6, y), color, -1)
    cv2.putText(img, text, (x + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw(frame: np.ndarray, result, fps: float | None = None) -> np.ndarray:
    img = frame.copy()
    for p in result.unverified:
        x1, y1, x2, y2 = map(int, p)
        cv2.rectangle(img, (x1, y1), (x2, y2), COLORS["unverified"], 1)
    for w in result.workers:
        c = COLORS[w.status]
        if w.person_box:
            x1, y1, x2, y2 = map(int, w.person_box)
            cv2.rectangle(img, (x1, y1), (x2, y2), c, 1)
        x1, y1, x2, y2 = map(int, w.box)
        cv2.rectangle(img, (x1, y1), (x2, y2), c, 2)
        text = {"compliant": "helmet", "at_risk": "no helmet?", "violation": f"NO HELMET {w.violation_s:.1f}s"}[w.status]
        _label(img, f"#{w.id} {text}", x1, y1 - 2, c)

    s = result.summary
    bar = f"{s['workers']} workers | {s['compliant']} ok | {s['violations']} violations"
    if s["at_risk"]:
        bar += f" | {s['at_risk']} at risk"
    if s["unverified"]:
        bar += f" | {s['unverified']} unverified"
    if fps:
        bar += f" | {fps:.0f} FPS"
    cv2.rectangle(img, (0, 0), (img.shape[1], 28), (30, 30, 30), -1)
    cv2.putText(img, bar, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                COLORS["violation"] if s["violations"] else (240, 240, 240), 1, cv2.LINE_AA)
    return img
