"""Add bounded live analytics; preserve immutable scenes and file results."""

import sqlalchemy as sa

from alembic import op

revision = "0010_live_capture_schema"
down_revision = "0009_live_capture"
branch_labels = None
depends_on = None

# Frozen DDL: this migration never imports application models.
_DDL = (
    """

CREATE TABLE worker_machines (
    machine_id VARCHAR(40) NOT NULL,
    worker_id VARCHAR(120) NOT NULL,
    owner_epoch UUID NOT NULL,
    heartbeat_at TIMESTAMP WITH TIME ZONE NOT NULL,
    capture_state VARCHAR(20) NOT NULL,
    reservation_id UUID,
    reserved_until TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (machine_id),
    CHECK (capture_state IN ('idle', 'probing', 'analyzing')),
    CHECK ((reservation_id IS NULL) = (reserved_until IS NULL))
)

""",
    """

CREATE TABLE live_sources (
    session_id UUID NOT NULL,
    machine_id VARCHAR(40) NOT NULL,
    device_index INTEGER NOT NULL,
    capture_backend VARCHAR(20) NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    reported_fps DOUBLE PRECISION,
    label_mode VARCHAR(20) NOT NULL,
    prepared_at TIMESTAMP WITH TIME ZONE NOT NULL,
    frame_checked_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (session_id),
    CHECK (device_index >= 0),
    CHECK (width BETWEEN 1 AND 1920 AND height BETWEEN 1 AND 1080),
    CHECK (label_mode IN ('directions', 'access')),
    CHECK (capture_backend IN ('dshow', 'msmf', 'auto', 'fake')),
    UNIQUE (session_id, machine_id),
    FOREIGN KEY(session_id) REFERENCES sessions (id),
    FOREIGN KEY(machine_id) REFERENCES worker_machines (machine_id)
)

""",
    """

CREATE TABLE live_analysis_states (
    job_id UUID NOT NULL,
    machine_id VARCHAR(40) NOT NULL,
    capture_status VARCHAR(30) NOT NULL,
    capture_started_at TIMESTAMP WITH TIME ZONE,
    capture_ended_at TIMESTAMP WITH TIME ZONE,
    elapsed_capture_seconds NUMERIC(12, 6) NOT NULL,
    last_capture_sequence BIGINT NOT NULL,
    last_analyzed_sequence BIGINT,
    current_segment_index INTEGER NOT NULL,
    stop_requested_at TIMESTAMP WITH TIME ZONE,
    retry_requested_at TIMESTAMP WITH TIME ZONE,
    resume_confirmed_at TIMESTAMP WITH TIME ZONE,
    checkpoint_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revision BIGINT NOT NULL,
    coverage_complete BOOLEAN NOT NULL,
    unknown_tail BOOLEAN NOT NULL,
    observed_seconds NUMERIC(12, 6) NOT NULL,
    missing_seconds NUMERIC(12, 6) NOT NULL,
    detector_parameters JSONB NOT NULL,
    unconfirmed_crossings INTEGER NOT NULL,
    sample_candidates_seen BIGINT NOT NULL,
    sample_capacity INTEGER NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (job_id),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    FOREIGN KEY(session_id, machine_id) REFERENCES live_sources (session_id, machine_id),
    CHECK (capture_status IN ('starting', 'connected', 'interrupted', 'awaiting_confirmation',
        'stopping', 'ended')),
    CHECK (elapsed_capture_seconds >= 0 AND last_capture_sequence >= 0),
    CHECK (current_segment_index >= 0 AND revision >= 0),
    CHECK (observed_seconds >= 0 AND missing_seconds >= 0),
    CHECK (unconfirmed_crossings >= 0 AND sample_candidates_seen >= 0),
    CHECK (sample_capacity = 20000)
)

""",
    """

CREATE TABLE live_capture_segments (
    id UUID NOT NULL,
    segment_index INTEGER NOT NULL,
    started_capture_seconds NUMERIC(12, 6) NOT NULL,
    ended_capture_seconds NUMERIC(12, 6),
    first_sequence BIGINT NOT NULL,
    last_sequence BIGINT,
    reason VARCHAR(20) NOT NULL,
    job_id UUID NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    UNIQUE (job_id, segment_index),
    UNIQUE (id, job_id, session_id),
    CHECK (segment_index >= 0 AND started_capture_seconds >= 0),
    CHECK (ended_capture_seconds IS NULL OR ended_capture_seconds >= started_capture_seconds),
    CHECK (first_sequence >= 0 AND (last_sequence IS NULL OR last_sequence >= first_sequence)),
    CHECK (reason IN ('initial', 'reconnected', 'analysis_gap'))
)

""",
    """

CREATE TABLE live_crossing_buckets (
    job_id UUID NOT NULL,
    shop_id UUID NOT NULL,
    bucket_index INTEGER NOT NULL,
    start_seconds NUMERIC(12, 6) NOT NULL,
    end_seconds NUMERIC(12, 6) NOT NULL,
    entries INTEGER NOT NULL,
    exits INTEGER NOT NULL,
    observed_seconds NUMERIC(12, 6) NOT NULL,
    missing_seconds NUMERIC(12, 6) NOT NULL,
    pending_count INTEGER NOT NULL,
    is_open BOOLEAN NOT NULL,
    coverage_incomplete BOOLEAN NOT NULL,
    unknown_tail BOOLEAN NOT NULL,
    revision BIGINT NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (job_id, shop_id, bucket_index),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    CHECK (bucket_index >= 0 AND start_seconds = 60 * bucket_index),
    CHECK (end_seconds BETWEEN start_seconds AND start_seconds + 60),
    CHECK (entries >= 0 AND exits >= 0 AND pending_count >= 0 AND revision >= 0),
    CHECK (observed_seconds BETWEEN 0 AND 60 AND missing_seconds BETWEEN 0 AND 60),
    CHECK (observed_seconds + missing_seconds <= end_seconds - start_seconds),
    FOREIGN KEY(shop_id) REFERENCES shops (id)
)

""",
    """

CREATE TABLE live_interruptions (
    id UUID NOT NULL,
    start_seconds NUMERIC(12, 6) NOT NULL,
    end_seconds NUMERIC(12, 6),
    reason VARCHAR(40) NOT NULL,
    end_known BOOLEAN NOT NULL,
    job_id UUID NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    CHECK (start_seconds >= 0 AND (end_seconds IS NULL OR end_seconds >= start_seconds)),
    CHECK (end_known = (end_seconds IS NOT NULL)),
    CHECK (reason IN ('capture_lost', 'analysis_gap', 'awaiting_confirmation',
        'worker_interrupted', 'database_unavailable'))
)

""",
    """

CREATE TABLE live_crossings (
    id UUID NOT NULL,
    segment_id UUID NOT NULL,
    shop_id UUID NOT NULL,
    track_id BIGINT NOT NULL,
    candidate_sequence BIGINT NOT NULL,
    capture_sequence BIGINT NOT NULL,
    capture_timestamp_seconds NUMERIC(12, 6) NOT NULL,
    confirmed_at_capture_seconds NUMERIC(12, 6) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    foot_x NUMERIC(9, 6) NOT NULL,
    foot_y NUMERIC(9, 6) NOT NULL,
    job_id UUID NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    FOREIGN KEY(segment_id, job_id, session_id) REFERENCES live_capture_segments (id, job_id,
        session_id),
    UNIQUE (job_id, candidate_sequence),
    CHECK (candidate_sequence >= 0 AND capture_sequence >= 0),
    CHECK (capture_timestamp_seconds >= 0 AND confirmed_at_capture_seconds >=
        capture_timestamp_seconds),
    CHECK (direction IN ('entry', 'exit')),
    CHECK (foot_x BETWEEN 0 AND 1 AND foot_y BETWEEN 0 AND 1),
    FOREIGN KEY(shop_id) REFERENCES shops (id)
)

""",
    """

CREATE TABLE live_position_samples (
    job_id UUID NOT NULL,
    slot_index INTEGER NOT NULL,
    segment_id UUID NOT NULL,
    track_id BIGINT NOT NULL,
    capture_sequence BIGINT NOT NULL,
    capture_timestamp_seconds NUMERIC(12, 6) NOT NULL,
    foot_x NUMERIC(9, 6) NOT NULL,
    foot_y NUMERIC(9, 6) NOT NULL,
    session_id UUID NOT NULL,
    PRIMARY KEY (job_id, slot_index),
    FOREIGN KEY(job_id, session_id) REFERENCES processing_jobs (id, session_id),
    FOREIGN KEY(segment_id, job_id, session_id) REFERENCES live_capture_segments (id, job_id,
        session_id),
    CHECK (slot_index >= 0 AND slot_index < 20000),
    CHECK (capture_sequence >= 0 AND capture_timestamp_seconds >= 0),
    CHECK (foot_x BETWEEN 0 AND 1 AND foot_y BETWEEN 0 AND 1)
)

""",
    """
CREATE INDEX ix_live_crossings_job_time ON live_crossings (job_id, capture_timestamp_seconds)
""",
)


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("target_machine_id", sa.String(40)))
    op.drop_constraint("ck_processing_jobs_video_analysis_scene", "processing_jobs", type_="check")
    op.create_check_constraint(
        "ck_processing_jobs_video_analysis_scene",
        "processing_jobs",
        "(kind IN ('video_analysis','live_analysis')) = "
        "(scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)",
    )
    for statement in _DDL:
        op.execute(statement)
    op.create_unique_constraint(
        "uq_live_state_job_session", "live_analysis_states", ["job_id", "session_id"]
    )
    for table in ("live_capture_segments", "live_interruptions"):
        op.create_foreign_key(
            f"fk_{table}_state",
            table,
            "live_analysis_states",
            ["job_id", "session_id"],
            ["job_id", "session_id"],
            deferrable=True,
            initially="DEFERRED",
        )
    op.execute("""
        CREATE FUNCTION flowsight_live_source_origin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM sessions s WHERE s.id = NEW.session_id AND s.source_kind = 'webcam'
            ) THEN
                RAISE EXCEPTION 'Live source requires webcam session' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'INSERT' AND NOT EXISTS (
                SELECT 1 FROM sessions s JOIN cameras c ON c.id = s.registered_camera_id
                WHERE s.id = NEW.session_id AND s.deleted_at IS NULL AND c.deleted_at IS NULL
            ) THEN
                RAISE EXCEPTION 'Live source requires active camera/session'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER live_source_origin
        AFTER INSERT OR UPDATE ON live_sources DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION flowsight_live_source_origin()
    """)
    _install_context_guards()


def _install_context_guards() -> None:
    op.execute("""
        CREATE FUNCTION flowsight_live_state_context() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM processing_jobs j WHERE j.id = NEW.job_id
                AND j.session_id = NEW.session_id AND j.kind = 'live_analysis'
                AND j.target_machine_id = NEW.machine_id AND j.frames_total IS NULL
            ) THEN
                RAISE EXCEPTION 'Invalid live job context' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER live_state_context
        AFTER INSERT OR UPDATE ON live_analysis_states DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION flowsight_live_state_context()
    """)
    op.execute("""
        CREATE FUNCTION flowsight_live_job_context() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM live_analysis_states WHERE job_id = OLD.id) AND (
                NEW.target_machine_id IS DISTINCT FROM OLD.target_machine_id OR
                NEW.session_id IS DISTINCT FROM OLD.session_id OR
                NEW.scene_version_id IS DISTINCT FROM OLD.scene_version_id OR
                NEW.registered_camera_id IS DISTINCT FROM OLD.registered_camera_id OR
                NEW.kind IS DISTINCT FROM OLD.kind OR NEW.frames_total IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'Live job context is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER live_job_context BEFORE UPDATE ON processing_jobs
        FOR EACH ROW EXECUTE FUNCTION flowsight_live_job_context()
    """)
    op.execute("""
        CREATE FUNCTION flowsight_live_session_origin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.source_kind IS DISTINCT FROM OLD.source_kind AND (
                OLD.source_kind = 'webcam' OR NEW.source_kind = 'webcam' OR
                EXISTS (SELECT 1 FROM live_sources WHERE session_id = OLD.id)
            ) THEN
                RAISE EXCEPTION 'Webcam session origin is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER live_session_origin BEFORE UPDATE OF source_kind ON sessions
        FOR EACH ROW EXECUTE FUNCTION flowsight_live_session_origin()
    """)
    op.execute("""
        CREATE FUNCTION flowsight_live_shop_context() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM processing_jobs j
                JOIN scene_version_shops vs ON vs.scene_version_id = j.scene_version_id
                JOIN live_analysis_states ls ON ls.job_id = j.id
                WHERE j.id = NEW.job_id AND j.session_id = NEW.session_id
                AND vs.shop_id = NEW.shop_id AND j.kind = 'live_analysis'
            ) THEN
                RAISE EXCEPTION 'Shop does not belong to live job scene' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    for table in ("live_crossings", "live_crossing_buckets"):
        op.execute(f"""
            CREATE CONSTRAINT TRIGGER live_shop_context
            AFTER INSERT OR UPDATE ON {table} DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION flowsight_live_shop_context()
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER live_job_context ON processing_jobs")
    op.execute("DROP TRIGGER live_session_origin ON sessions")
    op.drop_table("live_position_samples")
    op.drop_table("live_crossings")
    op.drop_table("live_interruptions")
    op.drop_table("live_crossing_buckets")
    op.drop_table("live_capture_segments")
    op.drop_table("live_analysis_states")
    op.drop_table("live_sources")
    op.execute("DROP FUNCTION flowsight_live_source_origin()")
    for name in ("state_context", "job_context", "session_origin", "shop_context"):
        op.execute(f"DROP FUNCTION flowsight_live_{name}()")
    op.drop_table("worker_machines")
    op.drop_constraint("ck_processing_jobs_video_analysis_scene", "processing_jobs", type_="check")
    _restore_video_scene_check()
    op.drop_column("processing_jobs", "target_machine_id")


def _restore_video_scene_check() -> None:
    """Restore the check that allows a scene only on video-analysis jobs.

    Live jobs created while the widened check was in force keep both references.
    Clearing them preserves the job. A video-analysis job that still lacks a
    scene is reported instead of receiving an invented one.
    """

    op.execute(
        sa.text(
            """
            UPDATE processing_jobs
            SET scene_version_id = NULL,
                registered_camera_id = NULL
            WHERE kind IS DISTINCT FROM 'video_analysis'
              AND scene_version_id IS NOT NULL
              AND registered_camera_id IS NOT NULL
            """
        )
    )
    invalid_count = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT count(*)
                FROM processing_jobs
                WHERE (kind = 'video_analysis')
                  IS DISTINCT FROM (
                        scene_version_id IS NOT NULL
                    AND registered_camera_id IS NOT NULL
                  )
                """
            )
        )
        .scalar_one()
    )
    if invalid_count:
        raise RuntimeError(
            "Cannot restore ck_processing_jobs_video_analysis_scene: "
            f"{invalid_count} video-analysis job(s) have no resolvable scene"
        )
    op.create_check_constraint(
        "ck_processing_jobs_video_analysis_scene",
        "processing_jobs",
        "(kind = 'video_analysis') = "
        "(scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)",
    )
