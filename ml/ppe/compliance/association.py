"""Match head/helmet boxes to person boxes."""

from __future__ import annotations

from collections.abc import Sequence

Box = Sequence[float]  # x1, y1, x2, y2


def _area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection_over_a(a: Box, b: Box) -> float:
    """Fraction of box ``a`` that lies inside box ``b``."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = _area(a)
    return ix * iy / area if area > 0 else 0.0


def associate_heads_to_persons(heads: Sequence[Box], persons: Sequence[Box],
                               min_ioa: float = 0.5, top_frac: float = 0.5) -> dict[int, int]:
    """Return ``{head_index: person_index}``.

    A head belongs to a person when most of the head box is inside the person
    box and the head's centre sits in the top ``top_frac`` of that box. Each
    person gets at most one head; ties go to the best overlap, then the smaller
    (tighter) person box, so a head in a crowd binds to the right body.
    """
    candidates = []
    for hi, h in enumerate(heads):
        cy = (h[1] + h[3]) / 2
        for pi, p in enumerate(persons):
            ioa = intersection_over_a(h, p)
            if ioa < min_ioa:
                continue
            if cy > p[1] + top_frac * (p[3] - p[1]):
                continue
            candidates.append((-ioa, _area(p), hi, pi))
    candidates.sort()
    match: dict[int, int] = {}
    used = set()
    for _, _, hi, pi in candidates:
        if hi in match or pi in used:
            continue
        match[hi] = pi
        used.add(pi)
    return match
