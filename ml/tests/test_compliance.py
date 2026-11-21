from ppe.compliance import ComplianceTracker, Observation, associate_heads_to_persons


def obs(tid, head, box=(0, 0, 10, 10)):
    return Observation(tid, head, 0.9, box)


def run(tracker, frames, fps=10):
    events = []
    for i, ob in enumerate(frames):
        events += tracker.update(i / fps, ob)
    return events


def test_association_prefers_containing_tight_person_and_top_half():
    persons = [(0, 0, 100, 300), (40, 0, 90, 150)]
    heads = [(50, 10, 70, 30), (10, 250, 30, 270)]   # 2nd head is at the feet of person 0
    assert associate_heads_to_persons(heads, persons) == {0: 1}


def test_association_one_head_per_person():
    persons = [(0, 0, 100, 300)]
    heads = [(10, 10, 30, 30), (60, 10, 80, 30)]
    assert len(associate_heads_to_persons(heads, persons)) == 1


def test_brief_bare_head_flicker_does_not_open_violation():
    t = ComplianceTracker(min_violation_s=1.0)
    frames = [[obs(1, False)]] * 10 + [[obs(1, True)]] * 3 + [[obs(1, False)]] * 10
    assert run(t, frames) == []
    assert t.workers[1].status == "compliant"


def test_sustained_bare_head_opens_one_event_then_closes_on_helmet():
    t = ComplianceTracker(min_violation_s=1.0, resolve_s=0.5)
    frames = [[obs(1, True)]] * 40 + [[obs(1, False)]] * 20
    ev = run(t, frames)
    assert [e.type for e in ev] == ["violation_started", "violation_ended"]
    assert ev[0].event_id == ev[1].event_id and ev[1].reason == "helmet_on"
    assert 3.0 <= ev[1].duration_s <= 4.5


def test_violation_closes_when_worker_leaves():
    t = ComplianceTracker(min_violation_s=0.5, lost_s=1.0)
    frames = [[obs(1, True)]] * 20 + [[]] * 15
    ev = run(t, frames)
    assert [e.type for e in ev] == ["violation_started", "violation_ended"]
    assert ev[1].reason == "lost" and 1 not in t.workers


def test_close_all_at_end_of_stream():
    t = ComplianceTracker(min_violation_s=0.2)
    run(t, [[obs(1, True), obs(2, False)]] * 10)
    ev = t.close_all(1.0)
    assert len(ev) == 1 and ev[0].worker_id == 1 and ev[0].reason == "stopped"
