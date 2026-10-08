"""Feature 009: additive schema and isolation, on a guarded local database."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import CheckConstraint, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession

from alembic import command
from flowsight.db.models import Base, Camera, JobKind, LiveSource, SourceKind, WorkerMachine
from flowsight.db.models import Session as FlowSession


@pytest.fixture
def live_database(monkeypatch: pytest.MonkeyPatch):
    url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", url)
    config = Config(BACKEND / "alembic.ini")
    engine = create_engine(url)
    if "processing_jobs" in inspect(engine).get_table_names():
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE processing_jobs CASCADE"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE processing_jobs CASCADE"))
        command.downgrade(config, "base")
        engine.dispose()


BACKEND = Path(__file__).resolve().parents[2]


def test_pause_migration_preserves_checkpoint_and_blocks_active_downgrade(live_job):
    from flowsight.db.models import JobStatus, LiveAnalysisState
    from flowsight.services.jobs import transition_job

    factory, job_id, _ = live_job
    config = Config(BACKEND / "alembic.ini")
    with factory.begin() as database:
        transition_job(
            database, job_id=job_id, target=JobStatus.PROCESSING, occurred_at=datetime.now(UTC)
        )
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "paused"
        state.pause_requested_at = state.paused_at = datetime.now(UTC)
        state.elapsed_capture_seconds = 120
        state.zone_dwell = {"sample": {"interior_average_seconds": 3}}
    with pytest.raises(RuntimeError, match="Stop paused webcam jobs"):
        command.downgrade(config, "0011_live_zone_dwell")
    with factory.begin() as database:
        database.get(LiveAnalysisState, job_id).capture_status = "ended"
        transition_job(
            database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=datetime.now(UTC)
        )
    command.downgrade(config, "0011_live_zone_dwell")
    with factory() as database:
        row = database.execute(
            text("SELECT elapsed_capture_seconds,zone_dwell FROM live_analysis_states")
        ).one()
        assert row[0] == 120 and row[1]["sample"]["interior_average_seconds"] == 3
    command.upgrade(config, "head")


@pytest.mark.parametrize(
    "violation",
    [
        "state_kind",
        "crossing_shop",
        "bucket_shop",
        "session_origin",
        "job_owner",
        "position_segment",
        "segment_without_state",
    ],
)
def test_live_schema_rejects_cross_context_writes(live_database, violation: str) -> None:
    from flowsight.db.models import (
        JobStatus,
        LiveAnalysisState,
        LiveCaptureSegment,
        LiveCrossing,
        LiveCrossingBucket,
        LivePositionSample,
        ProcessingJob,
        SceneVersion,
        SceneVersionShop,
        Shop,
    )

    now = datetime.now(UTC)
    with DatabaseSession(live_database) as database:
        machine = WorkerMachine(
            machine_id="isolation-machine",
            worker_id="worker",
            owner_epoch=uuid4(),
            heartbeat_at=now,
            capture_state="idle",
        )
        database.add(machine)
        pairs = []
        for index in range(2):
            camera = Camera(name=f"Camera{index}", name_key=f"camera{index}")
            database.add(camera)
            database.flush()
            session = FlowSession(
                name=f"Live{index}",
                camera_id=f"live-{index}",
                registered_camera_id=camera.id,
                source_kind=SourceKind.WEBCAM,
            )
            database.add(session)
            database.flush()
            database.add(
                LiveSource(
                    session_id=session.id,
                    machine_id=machine.machine_id,
                    device_index=0,
                    capture_backend="fake",
                    width=1280,
                    height=720,
                    label_mode="directions",
                    prepared_at=now,
                )
            )
            scene = SceneVersion(
                camera_id=camera.id,
                reference_session_id=session.id,
                version_number=1,
                frame_width=1280,
                frame_height=720,
            )
            shop = Shop(camera_id=camera.id)
            database.add_all([scene, shop])
            database.flush()
            database.add(
                SceneVersionShop(
                    scene_version_id=scene.id,
                    shop_id=shop.id,
                    camera_id=camera.id,
                    position=0,
                    name="Sector",
                    name_key="sector",
                )
            )
            job = ProcessingJob(
                session_id=session.id,
                registered_camera_id=camera.id,
                scene_version_id=scene.id,
                kind=JobKind.LIVE_ANALYSIS,
                target_machine_id=machine.machine_id,
                status=JobStatus.PENDING,
            )
            database.add(job)
            database.flush()
            state = LiveAnalysisState(
                job_id=job.id,
                session_id=session.id,
                machine_id=machine.machine_id,
                checkpoint_at=now,
            )
            segment = LiveCaptureSegment(
                job_id=job.id,
                session_id=session.id,
                segment_index=0,
                started_capture_seconds=0,
                first_sequence=0,
                reason="initial",
            )
            database.add_all([state, segment])
            database.flush()
            pairs.append((session, job, shop, segment))
        database.commit()
        session, job, shop, segment = pairs[0]
        other_shop, other_segment = pairs[1][2:]
        with pytest.raises(IntegrityError):
            if violation in ("state_kind", "segment_without_state"):
                synthetic = ProcessingJob(
                    session_id=session.id,
                    kind=JobKind.SYNTHETIC_BASE_FLOW,
                    status=JobStatus.PENDING,
                    target_machine_id=machine.machine_id,
                )
                database.add(synthetic)
                database.flush()
                if violation == "state_kind":
                    database.add(
                        LiveAnalysisState(
                            job_id=synthetic.id,
                            session_id=session.id,
                            machine_id=machine.machine_id,
                            checkpoint_at=now,
                        )
                    )
                else:
                    database.add(
                        LiveCaptureSegment(
                            job_id=synthetic.id,
                            session_id=session.id,
                            segment_index=0,
                            started_capture_seconds=0,
                            first_sequence=0,
                            reason="initial",
                        )
                    )
            elif violation == "crossing_shop":
                database.add(
                    LiveCrossing(
                        job_id=job.id,
                        session_id=session.id,
                        segment_id=segment.id,
                        shop_id=other_shop.id,
                        track_id=1,
                        candidate_sequence=1,
                        capture_sequence=1,
                        capture_timestamp_seconds=0,
                        confirmed_at_capture_seconds=1,
                        direction="entry",
                        foot_x=0.5,
                        foot_y=0.5,
                    )
                )
            elif violation == "bucket_shop":
                database.add(
                    LiveCrossingBucket(
                        job_id=job.id,
                        session_id=session.id,
                        shop_id=other_shop.id,
                        bucket_index=0,
                        start_seconds=0,
                        end_seconds=1,
                    )
                )
            elif violation == "session_origin":
                session.source_kind = SourceKind.SYNTHETIC
            elif violation == "job_owner":
                job.target_machine_id = "another-machine"
            else:
                database.add(
                    LivePositionSample(
                        job_id=job.id,
                        session_id=session.id,
                        segment_id=other_segment.id,
                        slot_index=0,
                        track_id=1,
                        capture_sequence=0,
                        capture_timestamp_seconds=0,
                        foot_x=0.5,
                        foot_y=0.5,
                    )
                )
            database.commit()
        database.rollback()


def test_live_origins_are_distinct_from_video_and_synthetic() -> None:
    assert SourceKind.WEBCAM.value == "webcam"
    assert JobKind.LIVE_ANALYSIS.value == "live_analysis"


def test_live_metadata_has_scoped_tables_and_bounded_samples() -> None:
    expected = {
        "worker_machines",
        "live_sources",
        "live_analysis_states",
        "live_capture_segments",
        "live_interruptions",
        "live_crossings",
        "live_crossing_buckets",
        "live_position_samples",
    }
    assert expected <= set(Base.metadata.tables)
    samples = Base.metadata.tables["live_position_samples"]
    assert {column.name for column in samples.primary_key.columns} == {"job_id", "slot_index"}
    assert any(
        "20000" in str(constraint.sqltext)
        for constraint in samples.constraints
        if isinstance(constraint, CheckConstraint)
    )


def test_upgrade_from_0008_adds_bounded_live_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", url)
    config = Config(BACKEND / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0008_scene_configuration_removal")
    engine = create_engine(url)
    try:
        old_tables = set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        tables = set(inspect(engine).get_table_names())
        assert old_tables <= tables
        assert {
            "worker_machines",
            "live_sources",
            "live_analysis_states",
            "live_capture_segments",
            "live_interruptions",
            "live_crossings",
            "live_crossing_buckets",
            "live_position_samples",
        } <= tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 'webcam'::source_kind::text")) == "webcam"
            assert connection.scalar(text("SELECT 'live_analysis'::job_kind::text")) == (
                "live_analysis"
            )
        sample_checks = inspect(engine).get_check_constraints("live_position_samples")
        assert any("20000" in item["sqltext"] for item in sample_checks)
        # Invalid slot must fail before a sample can enter historical analytics.
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO live_position_samples "
                        "(job_id,slot_index,session_id,segment_id,track_id,capture_sequence,"
                        "capture_timestamp_seconds,foot_x,foot_y) VALUES "
                        "(gen_random_uuid(),20000,gen_random_uuid(),gen_random_uuid(),1,1,0,.5,.5)"
                    )
                )
        with DatabaseSession(engine) as database:
            camera = Camera(name="Schema", name_key="schema")
            machine = WorkerMachine(
                machine_id="schema-machine",
                worker_id="schema-worker",
                owner_epoch=uuid4(),
                heartbeat_at=datetime.now(UTC),
                capture_state="idle",
            )
            database.add_all([camera, machine])
            database.flush()
            session = FlowSession(
                name="No webcam",
                camera_id="schema",
                registered_camera_id=camera.id,
                source_kind=SourceKind.SYNTHETIC,
            )
            database.add(session)
            database.commit()
            with pytest.raises(IntegrityError):
                database.add(
                    LiveSource(
                        session_id=session.id,
                        machine_id=machine.machine_id,
                        device_index=0,
                        capture_backend="fake",
                        width=1280,
                        height=720,
                        label_mode="directions",
                        prepared_at=datetime.now(UTC),
                    )
                )
                database.commit()
            database.rollback()
    finally:
        engine.dispose()
        command.downgrade(config, "base")
