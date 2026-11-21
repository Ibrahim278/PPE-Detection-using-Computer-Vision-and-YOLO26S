from ppe.data.prepare import stratified_split
from ppe.data.voc import Annotation, Box, to_yolo_lines


def test_to_yolo_drops_unknown_and_clips():
    ann = Annotation("a.png", 100, 200, [
        Box("helmet", 10, 20, 30, 60),
        Box("person", 0, 0, 50, 50),       # dropped class
        Box("head", 90, 190, 120, 230),    # clipped to image
        Box("head", 5, 5, 5.5, 5.5),       # degenerate
    ])
    lines = to_yolo_lines(ann, {"helmet": 0, "head": 1})
    assert len(lines) == 2
    assert lines[0] == "0 0.200000 0.200000 0.200000 0.200000"
    cls, cx, cy, w, h = lines[1].split()
    assert cls == "1" and float(cx) + float(w) / 2 <= 1.0 and float(cy) + float(h) / 2 <= 1.0


def test_stratified_split_keeps_proportions_and_is_disjoint():
    keys = {f"img{i}": int(i % 4 == 0) for i in range(1000)}
    s = stratified_split(keys, {"train": 0.7, "val": 0.2, "test": 0.1}, seed=42)
    all_names = s["train"] + s["val"] + s["test"]
    assert len(all_names) == len(set(all_names)) == 1000
    for split, frac in [("train", 0.7), ("val", 0.2), ("test", 0.1)]:
        pos = sum(keys[n] for n in s[split]) / len(s[split])
        assert abs(pos - 0.25) < 0.02
        assert abs(len(s[split]) / 1000 - frac) < 0.01
    assert s == stratified_split(keys, {"train": 0.7, "val": 0.2, "test": 0.1}, seed=42)
