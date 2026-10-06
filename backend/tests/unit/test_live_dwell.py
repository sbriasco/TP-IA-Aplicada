from decimal import Decimal
from uuid import uuid4

import pytest

from flowsight.vision.live_dwell import LiveDwellCounter
from flowsight.vision.spatial import ShopGeometry


def make_counter():
    shop = ShopGeometry(
        uuid4(),
        "Local",
        [(0, 0), (1, 0), (1, 0.4), (0, 0.4)],
        [(0, 0.6), (1, 0.6), (1, 1), (0, 1)],
        None,
        None,
        None,
    )
    return LiveDwellCounter([shop]), str(shop.shop_id)


def test_positive_active_and_finished_visits_exclude_single_observations():
    counter, shop_id = make_counter()
    counter.observe(Decimal(0), 0, {1: (0.5, 0.8), 2: (0.5, 0.2)})
    counter.observe(Decimal(".5"), 0, {1: (0.5, 0.8), 2: (0.5, 0.2), 3: (0.5, 0.8)})
    counter.observe(Decimal("1"), 0, {1: (0.5, 0.8)})
    summary = counter.snapshot()[shop_id]
    assert summary["interior_average_seconds"] == 1
    assert summary["interior_sample_count"] == 1
    assert summary["front_average_seconds"] == 0.5
    assert summary["front_sample_count"] == 1


def test_loss_gap_and_segments_never_infer_unseen_time():
    counter, shop_id = make_counter()
    for timestamp, segment, feet in [
        ("0", 0, {1: (0.5, 0.8)}),
        (".5", 0, {1: (0.5, 0.8)}),
        ("1", 0, {}),
        ("5", 0, {1: (0.5, 0.8)}),
        ("5.5", 0, {1: (0.5, 0.8)}),
        ("10", 1, {1: (0.5, 0.8)}),
        ("10.5", 1, {1: (0.5, 0.8)}),
    ]:
        counter.observe(Decimal(timestamp), segment, feet)
    assert counter.snapshot()[shop_id]["interior_average_seconds"] == 0.5
    assert counter.snapshot()[shop_id]["interior_sample_count"] == 3
    counter.observe(Decimal("10.5"), 1, {1: (0.5, 0.8)})
    assert counter.snapshot()[shop_id]["interior_sample_count"] == 3
    other, other_id = make_counter()
    assert other.snapshot()[other_id]["interior_average_seconds"] is None


def test_transition_invalid_feet_and_bounded_tracking():
    counter, shop_id = make_counter()
    counter.observe(Decimal(0), 0, {1: (0.5, 0.8)})
    counter.observe(Decimal(".5"), 0, {1: (0.5, 0.8)})
    counter.observe(Decimal("1"), 0, {1: (0.5, 0.2), 2: (float("nan"), 0.8)})
    counter.observe(Decimal("1.5"), 0, {1: (0.5, 0.2)})
    assert counter.snapshot()[shop_id]["interior_average_seconds"] == 0.5
    assert counter.snapshot()[shop_id]["front_average_seconds"] == 0.5


def test_tracking_limit_does_not_extend_evicted_observations():
    shop = ShopGeometry(uuid4(), "Local", None, [(0, 0), (1, 0), (1, 1), (0, 1)], None, None, None)
    counter = LiveDwellCounter([shop], max_tracks=1)
    counter.observe(Decimal(0), 0, {1: (0.5, 0.5)})
    counter.observe(Decimal(".5"), 0, {1: (0.5, 0.5)})
    counter.observe(Decimal("1"), 0, {1: (0.5, 0.5), 2: (0.5, 0.5)})
    counter.observe(Decimal("1.5"), 0, {2: (0.5, 0.5)})
    assert counter.snapshot()[str(shop.shop_id)]["interior_average_seconds"] == 0.75
    assert counter.snapshot()[str(shop.shop_id)]["interior_sample_count"] == 2


@pytest.mark.parametrize("limit", [0, -1, 2049])
def test_rejects_invalid_tracking_limit(limit):
    with pytest.raises(ValueError):
        LiveDwellCounter([], max_tracks=limit)
