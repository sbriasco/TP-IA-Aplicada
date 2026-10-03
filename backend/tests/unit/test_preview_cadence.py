"""Preview images stay at the websocket cap. Analysis still sees every frame."""

from flowsight.worker.video_analysis import preview_is_due


def test_preview_starts_immediately_then_waits_for_the_cap() -> None:
    assert preview_is_due(
        frame_index=0, frames_total=50, now_s=0.01, last_publish_s=None, max_fps=5
    )
    assert not preview_is_due(
        frame_index=1, frames_total=50, now_s=0.19, last_publish_s=0.01, max_fps=5
    )
    assert preview_is_due(
        frame_index=20, frames_total=50, now_s=0.21, last_publish_s=0.01, max_fps=5
    )


def test_a_fifty_frame_clip_publishes_four_images_when_frames_are_ten_milliseconds_apart() -> None:
    last: float | None = None
    published: list[int] = []
    for frame_index in range(50):
        now_s = (frame_index + 1) * 0.01
        if preview_is_due(
            frame_index=frame_index,
            frames_total=50,
            now_s=now_s,
            last_publish_s=last,
            max_fps=5,
        ):
            published.append(frame_index)
            last = now_s
    assert published == [0, 20, 40, 49]


def test_the_last_frame_is_published_even_inside_the_interval() -> None:
    assert preview_is_due(
        frame_index=49, frames_total=50, now_s=0.05, last_publish_s=0.0, max_fps=5
    )
