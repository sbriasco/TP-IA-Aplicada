from flowsight.vision.live_performance import LivePerformance


def test_fps_uses_recent_deltas_not_absolute_sequence_or_model_warmup():
    metrics = LivePerformance()
    assert metrics.observe(1000, 10, 100) == (None, None)
    assert metrics.observe(1030, 11, 101) == (30, 1)
    for second in range(12, 21):
        capture, analysis = metrics.observe(
            1030 + (second - 11) * 60, second, 101 + (second - 11) * 2
        )
    assert capture == 60
    assert analysis == 0.5
    assert len(metrics.points) <= 6
    metrics.reset()
    assert metrics.observe(2000, 30, 200) == (None, None)
