"""Process one claimed `video_analysis` job and write its trajectory sample."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import sessionmaker

from flowsight.core.config import Settings
from flowsight.db.models import (
    JobStatus,
    ProcessingJob,
    SceneEntryLine,
    SceneVersionShop,
    SceneZone,
    VideoSource,
    ZoneRole,
)
from flowsight.preview.broker import PreviewUpdate
from flowsight.preview.snapshot import snapshot_path, write_preview_snapshot
from flowsight.services.jobs import transition_job
from flowsight.services.measures import close_measures, sync_measures
from flowsight.services.scene_metrics import persist_completed_scene
from flowsight.video.decode import iter_video_frames
from flowsight.video.storage import video_path
from flowsight.vision.detector import Detection, Detector, ModelUnavailable, build_detector
from flowsight.vision.events import SceneEventRecorder
from flowsight.vision.evidence import build_reference_summary, write_reference_summary
from flowsight.vision.overlay import render_overlay_jpeg
from flowsight.vision.spatial import ShopGeometry, SpatialCounter, normalized_foot
from flowsight.vision.trajectory import TrajectoryWriter, trajectory_relative_path

logger = logging.getLogger(__name__)

FLUSH_EVERY_FRAMES = 15


def _monotonic() -> float:
    return time.monotonic()


def preview_is_due(
    *,
    frame_index: int,
    frames_total: int,
    now_s: float,
    last_publish_s: float | None,
    max_fps: int,
) -> bool:
    """True for the first frame, the last frame, and at most `max_fps` images per second."""

    if frame_index == 0 or frame_index + 1 == frames_total:
        return True
    if last_publish_s is None:
        return True
    # A gap that lands on the interval must count. Binary fractions of 0.2 s sit just below it.
    return now_s - last_publish_s + 1e-6 >= 1 / max_fps

_FAILURE_MESSAGES = {
    "video_unavailable": "El video de la sesión no está en este equipo.",
    "model_unavailable": "El modelo de detección no está disponible.",
    "analysis_failed": "El análisis del video no pudo completarse.",
}


class _AnalysisError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def process_video_analysis_job(
    factory: sessionmaker[DatabaseSession],
    job_id: uuid.UUID,
    *,
    settings: Settings | None,
    now: Callable[[], datetime],
) -> None:
    if settings is None or settings.videos_dir is None:
        _fail(factory, job_id, "video_unavailable", now())
        return
    try:
        detector = build_detector(settings)
    except ModelUnavailable:
        _fail(factory, job_id, "model_unavailable", now())
        return
    try:
        _run(factory, job_id, settings, detector, now)
    except _AnalysisError as error:
        _fail(factory, job_id, error.code, now())
    except Exception:
        logger.exception("video_analysis failed job_id=%s", job_id)
        _fail(factory, job_id, "analysis_failed", now())


def _run(
    factory: sessionmaker[DatabaseSession],
    job_id: uuid.UUID,
    settings: Settings,
    detector: Detector,
    now: Callable[[], datetime],
) -> None:
    with factory.begin() as database_session:
        job = database_session.get(ProcessingJob, job_id)
        source = database_session.get(VideoSource, job.session_id) if job is not None else None
        if job is None or source is None or settings.videos_dir is None:
            raise _AnalysisError("video_unavailable")
        try:
            path = video_path(settings.videos_dir, source.relative_path)
        except ValueError as error:
            raise _AnalysisError("video_unavailable") from error
        if not path.is_file():
            raise _AnalysisError("video_unavailable")
        frames_total = source.frame_count
        width = source.width
        height = source.height
        fps = source.fps
        relative = trajectory_relative_path(job.session_id, job.id)
        zones, entry_line, shops = _scene_context(database_session, job.scene_version_id)
        job.frames_total = frames_total
        job.detector_name = detector.name
        job.detector_version = detector.version
        job.tracker_name = detector.tracker_name
        job.tracker_version = detector.tracker_version
        job.trajectory_relative_path = relative
        session_id = job.session_id

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise _AnalysisError("video_unavailable")
    writer = TrajectoryWriter(
        settings.videos_dir / relative,
        session_id=session_id,
        job_id=job_id,
        detector_name=detector.name,
        detector_version=detector.version,
        tracker_name=detector.tracker_name,
        tracker_version=detector.tracker_version,
    )
    counter = SpatialCounter(shops)
    recorder = SceneEventRecorder(shops, fps=float(fps))
    frame_index = 0
    cancelled = False
    last_preview_s: float | None = None
    try:
        for ok, decoded in iter_video_frames(capture, frames_total):
            frame = cast(np.ndarray, decoded)
            if not ok:
                raise _AnalysisError("analysis_failed")
            timestamp = (Decimal(frame_index) / Decimal(str(fps))).quantize(Decimal("0.000001"))
            detections = detector.detect(frame_index, width, height, frame)
            writer.observe(
                frame_index,
                timestamp,
                detections,
                width=width,
                height=height,
            )
            facts = counter.observe(frame_index, detections, width=width, height=height)
            feet = [
                (detection.track_id, normalized_foot(detection, width, height))
                for detection in detections
            ]
            recorder.observe(frame_index, feet, facts)
            frames_analyzed = frame_index + 1
            if frames_analyzed == frames_total:
                finished = counter.finish()
                facts.extend(finished)
                recorder.accept_crossings(finished)
            if _should_flush(frames_analyzed, frames_total, facts):
                with factory.begin() as database_session:
                    stored = database_session.get(ProcessingJob, job_id)
                    if stored is None or stored.status not in {
                        JobStatus.PROCESSING,
                        JobStatus.CANCELLED,
                    }:
                        raise _AnalysisError("analysis_failed")
                    cancelled = stored.status is JobStatus.CANCELLED
                    stored.frames_analyzed = frames_analyzed
                    stored.analyzed_video_timestamp_seconds = timestamp
                    sync_measures(
                        database_session,
                        job_id=job_id,
                        session_id=session_id,
                        video_timestamp_seconds=timestamp,
                        counts=counter.counts(),
                        facts=facts,
                        fps=fps,
                    )
            now_s = _monotonic()
            if preview_is_due(
                frame_index=frame_index,
                frames_total=frames_total,
                now_s=now_s,
                last_publish_s=last_preview_s,
                max_fps=settings.preview_max_fps,
            ):
                _publish_preview(
                    settings,
                    session_id=session_id,
                    job_id=job_id,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    frames_total=frames_total,
                    frame=frame,
                    detections=detections,
                    zones=zones,
                    entry_line=entry_line,
                    measures=counter.measure_payloads(partial=True),
                )
                last_preview_s = now_s
            frame_index += 1
            if cancelled:
                break
    finally:
        capture.release()
        writer.close()

    if cancelled:
        return
    if frame_index != frames_total:
        raise _AnalysisError("analysis_failed")
    evidence = None
    with factory.begin() as database_session:
        close_measures(database_session, job_id)
        persist_completed_scene(
            database_session,
            job_id=job_id,
            session_id=session_id,
            events=recorder.finish(),
            fps=float(fps),
            duration_seconds=frames_total / float(fps),
            front_by_shop={shop.shop_id: bool(shop.front_polygon) for shop in shops},
            line_by_shop={shop.shop_id: shop.line_start is not None for shop in shops},
        )
        finished = transition_job(
            database_session,
            job_id=job_id,
            target=JobStatus.COMPLETED,
            occurred_at=now(),
        )
        mode = getattr(detector, "execution_mode", None)
        if isinstance(mode, str):
            duration_ms = finished.processing_duration_ms or 0
            evidence = build_reference_summary(
                execution_mode=mode,
                detector_name=detector.name,
                detector_version=detector.version,
                tracker_name=detector.tracker_name,
                tracker_version=detector.tracker_version,
                frames_total=frames_total,
                processing_duration_s=duration_ms / 1000,
                limitations=list(getattr(detector, "limitations", ())),
            )
            evidence_session_id = finished.session_id
    if evidence is not None and settings.videos_dir is not None:
        relative = f"derived/{evidence_session_id}/{job_id}/evidence.json"
        write_reference_summary(settings.videos_dir / relative, evidence)


def _should_flush(frames_analyzed: int, frames_total: int, facts: Sequence[object]) -> bool:
    """Persist on each decided crossing, every 15 frames, and on the last frame."""

    return (
        frames_analyzed == frames_total
        or frames_analyzed % FLUSH_EVERY_FRAMES == 0
        or bool(facts)
    )


def _scene_context(
    database_session: DatabaseSession, scene_version_id: uuid.UUID | None
) -> tuple[
    list[list[tuple[float, float]]],
    tuple[tuple[float, float], tuple[float, float]] | None,
    list[ShopGeometry],
]:
    zones: list[list[tuple[float, float]]] = []
    entry_line = None
    shops: list[ShopGeometry] = []
    if scene_version_id is None:
        return zones, entry_line, shops
    version_shops = database_session.scalars(
        select(SceneVersionShop)
        .where(SceneVersionShop.scene_version_id == scene_version_id)
        .order_by(SceneVersionShop.position)
    ).all()
    for shop in version_shops:
        front = None
        interior = None
        window = None
        for zone in database_session.scalars(
            select(SceneZone).where(SceneZone.version_shop_id == shop.id)
        ):
            polygon = [(float(point[0]), float(point[1])) for point in zone.polygon]
            zones.append(polygon)
            if zone.role is ZoneRole.FRONT:
                front = polygon
            elif zone.role is ZoneRole.INTERIOR:
                interior = polygon
            elif zone.role is ZoneRole.SHOWCASE:
                window = polygon
        entry = database_session.get(SceneEntryLine, shop.id)
        line_start = None
        line_end = None
        direction: Literal["a_to_b", "b_to_a"] | None = None
        if entry is not None:
            line_start = (float(entry.start_x), float(entry.start_y))
            line_end = (float(entry.end_x), float(entry.end_y))
            if entry.entry_direction.value in {"a_to_b", "b_to_a"}:
                direction = cast("Literal['a_to_b', 'b_to_a']", entry.entry_direction.value)
            if entry_line is None:
                entry_line = (line_start, line_end)
        shops.append(
            ShopGeometry(
                shop_id=shop.shop_id,
                shop_name=shop.name,
                front_polygon=front,
                interior_polygon=interior,
                line_start=line_start,
                line_end=line_end,
                entry_direction=direction,
                window_polygon=window,
            )
        )
    return zones, entry_line, shops


def _publish_preview(
    settings: Settings,
    *,
    session_id: uuid.UUID,
    job_id: uuid.UUID,
    frame_index: int,
    timestamp: Decimal,
    frames_total: int,
    frame: np.ndarray,
    detections: Sequence[Detection],
    zones: Sequence[Sequence[Sequence[float]]],
    entry_line: tuple[Sequence[float], Sequence[float]] | None,
    measures: Sequence[Mapping[str, object]] = (),
) -> None:
    if settings.videos_dir is None or frames_total <= 0:
        return
    try:
        jpeg = render_overlay_jpeg(frame, detections, zones, entry_line)
    except Exception:
        return
    progress = (frame_index + 1) / frames_total * 100
    update = PreviewUpdate(
        session_id=session_id,
        job_id=job_id,
        frame_index=frame_index,
        video_timestamp_seconds=timestamp,
        progress_percent=progress,
        image_base64=base64.b64encode(jpeg).decode("ascii"),
        schema_version="2",
        measures=tuple(dict(item) for item in measures),
    )
    try:
        write_preview_snapshot(snapshot_path(settings.videos_dir, session_id, job_id), update)
    except OSError:
        return


def _fail(
    factory: sessionmaker[DatabaseSession],
    job_id: uuid.UUID,
    code: str,
    occurred_at: datetime,
) -> None:
    with factory.begin() as database_session:
        job = database_session.get(ProcessingJob, job_id)
        if job is None or job.status is not JobStatus.PROCESSING:
            return
        transition_job(
            database_session,
            job_id=job_id,
            target=JobStatus.FAILED,
            occurred_at=occurred_at,
            reason_code=code,
            failure_message=_FAILURE_MESSAGES[code],
        )
