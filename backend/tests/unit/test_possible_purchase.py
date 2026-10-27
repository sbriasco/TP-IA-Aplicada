"""Pure possible-purchase rule: exclusive bag overlap over video time."""

from __future__ import annotations

from flowsight.vision.detector import BagBox, Detection
from flowsight.vision.possible_purchase import PossiblePurchaseRecorder

FPS = 10.0
PERSON = (10.0, 10.0, 50.0, 90.0)
BAG_ON_PERSON = (20.0, 40.0, 45.0, 70.0)
BAG_ELSEWHERE = (200.0, 200.0, 240.0, 240.0)
PERSON_B = (100.0, 10.0, 140.0, 90.0)
BAG_ON_BOTH = (40.0, 20.0, 120.0, 80.0)


def _run(
    frames: list[tuple[list[Detection], list[BagBox]]],
    *,
    fps: float = FPS,
) -> tuple[int, tuple[int, ...]]:
    recorder = PossiblePurchaseRecorder(fps=fps)
    for index, (persons, bags) in enumerate(frames):
        recorder.observe(index, persons, bags)
    draft = recorder.finish()
    return draft.visit_count, draft.track_ids


def test_exclusive_overlap_of_one_second_counts_once() -> None:
    # 0..10 inclusive = 1.0 s at 10 fps
    frames = [
        ([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)]) for _ in range(11)
    ]
    count, tracks = _run(frames)
    assert count == 1
    assert tracks == (1,)


def test_overlap_under_one_second_does_not_count() -> None:
    frames = [([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)]) for _ in range(9)]
    count, tracks = _run(frames)
    assert count == 0
    assert tracks == ()


def test_gap_up_to_one_second_keeps_the_same_run() -> None:
    on = ([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)])
    off = ([Detection(1, PERSON)], [])
    # last exclusive at frame 5; 9 frames without; resume at 15 → gap 1.0 s
    frames = [on] * 6 + [off] * 9 + [on] * 5
    count, tracks = _run(frames)
    assert count == 1
    assert tracks == (1,)


def test_gap_over_one_second_closes_the_run() -> None:
    on = ([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)])
    off = ([Detection(1, PERSON)], [])
    # 5 exclusive (<1s), gap >1s, then 5 more (<1s each) → neither run confirms
    frames = [on] * 5 + [off] * 12 + [on] * 5
    count, _tracks = _run(frames)
    assert count == 0


def test_lost_track_closes_the_run() -> None:
    on = ([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)])
    gone = ([], [])
    frames = [on] * 5 + [gone] * 12 + [([Detection(2, PERSON)], [BagBox(BAG_ON_PERSON)])] * 11
    count, tracks = _run(frames)
    assert count == 1
    assert tracks == (2,)


def test_bag_on_two_or_zero_persons_does_not_count() -> None:
    both = (
        [Detection(1, PERSON), Detection(2, PERSON_B)],
        [BagBox(BAG_ON_BOTH)],
    )
    none = ([Detection(1, PERSON)], [BagBox(BAG_ELSEWHERE)])
    frames = [both] * 15 + [none] * 15
    count, tracks = _run(frames)
    assert count == 0
    assert tracks == ()


def test_same_visit_after_cut_still_counts_once() -> None:
    on = ([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)])
    gap = ([Detection(1, PERSON)], [])
    frames = [on] * 11 + [gap] * 12 + [on] * 11
    count, tracks = _run(frames)
    assert count == 1
    assert tracks == (1,)


def test_video_end_keeps_a_confirmed_run() -> None:
    frames = [([Detection(1, PERSON)], [BagBox(BAG_ON_PERSON)]) for _ in range(11)]
    count, tracks = _run(frames)
    assert count == 1
    assert tracks == (1,)


def test_zero_visits_is_available_zero() -> None:
    frames = [([Detection(1, PERSON)], []) for _ in range(20)]
    count, tracks = _run(frames)
    assert count == 0
    assert tracks == ()
    draft = PossiblePurchaseRecorder(fps=FPS).finish()
    assert draft.availability == "available"
    assert draft.visit_count == 0
