"""Bounded historical positions, without frames or video."""

from decimal import Decimal
from random import Random

from flowsight.vision.live_sampling import LivePositionSampler


def test_sample_is_bounded_and_one_candidate_per_track_second() -> None:
    sampler = LivePositionSampler(capacity=3, rng=Random(4), max_tracks=4)
    for sequence in range(100):
        timestamp = Decimal(sequence) / 10
        sampler.observe(
            segment_index=0,
            track_id=7,
            sequence=sequence,
            timestamp_s=timestamp,
            foot=(0.5, 0.5),
        )
    assert sampler.candidates_seen == 10
    assert len(sampler.samples) == 3
    assert set(sampler.samples) <= {0, 1, 2}
    assert len(sampler.drain_changes()) <= 3
    assert sampler.drain_changes() == []


def test_reused_id_in_another_segment_is_a_new_sample_candidate() -> None:
    sampler = LivePositionSampler(capacity=4, rng=Random(4))
    for segment in (0, 1):
        sampler.observe(
            segment_index=segment,
            track_id=7,
            sequence=segment,
            timestamp_s=Decimal(".1"),
            foot=(0.5, 0.5),
        )
    assert sampler.candidates_seen == 2
    assert {sample.segment_index for sample in sampler.samples.values()} == {0, 1}


def test_inactive_metadata_expires_and_capacity_never_grows() -> None:
    sampler = LivePositionSampler(capacity=3, rng=Random(4), max_tracks=4)
    for track in range(20):
        sampler.observe(
            segment_index=0,
            track_id=track,
            sequence=track,
            timestamp_s=Decimal(track),
            foot=(0.5, 0.5),
        )
        assert sampler.tracked_count <= 4
    assert sampler.tracked_count == 1
    assert len(sampler.samples) == 3


def test_invalid_positions_are_not_candidates() -> None:
    sampler = LivePositionSampler(capacity=3, rng=Random(4))
    for foot in ((-1.0, 0.5), (float("nan"), 0.5), (0.5, 2.0)):
        sampler.observe(
            segment_index=0,
            track_id=7,
            sequence=1,
            timestamp_s=Decimal(".1"),
            foot=foot,
        )
    assert sampler.candidates_seen == 0
    assert sampler.samples == {}
