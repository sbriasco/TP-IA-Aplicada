"""One active worker/device per machine; independent PCs can share PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from flowsight.db.models import Camera, JobKind, JobStatus, ProcessingJob, SourceKind, WorkerMachine
from flowsight.db.models import Session as FlowSession
from flowsight.worker.lifecycle import claim_next_job, recover_interrupted_jobs
from flowsight.worker.live_control import (
    LiveMachineError,
    MachineLease,
    release_reservation,
    reserve_machine,
)


def test_live_pending_job_still_blocks_file_queue_admission(live_job):
    from flowsight.services.jobs import JobRequestError, create_job_for_session

    factory, job_id, _ = live_job
    with factory.begin() as database:
        live = database.get(ProcessingJob, job_id)
        session = FlowSession(
            name="File queue blocked by live",
            camera_id="synthetic",
            registered_camera_id=live.registered_camera_id,
            source_kind=SourceKind.SYNTHETIC,
        )
        database.add(session)
        database.flush()
        with pytest.raises(JobRequestError, match="machine_busy"):
            create_job_for_session(
                database,
                session,
                JobKind.SYNTHETIC_BASE_FLOW,
                None,
                target_machine_id="expo-runner",
            )


def test_machine_advisory_lock_is_exclusive_and_released(live_engine) -> None:
    now = datetime.now(UTC)
    first = MachineLease(live_engine, "machine-one", "worker-one")
    second = MachineLease(live_engine, "machine-one", "worker-two")
    other = MachineLease(live_engine, "machine-two", "worker-other")
    try:
        assert first.acquire(now)
        assert first.acquire(now)  # no recursive advisory lock acquisition
        assert not second.acquire(now)
        assert other.acquire(now)
        first.release()
        assert second.acquire(now)
        with Session(live_engine) as database:
            assert database.get(WorkerMachine, "machine-one").worker_id == "worker-two"
    finally:
        first.release()
        second.release()
        other.release()


def test_probe_reservation_busy_expiry_and_stale_release(live_engine) -> None:
    now = datetime.now(UTC)
    lease = MachineLease(live_engine, "machine-one", "worker-one")
    assert lease.acquire(now)
    try:
        with Session(live_engine) as database:
            first = reserve_machine(database, "machine-one", now)
            database.commit()
            with pytest.raises(LiveMachineError, match="machine_busy"):
                reserve_machine(database, "machine-one", now)
            database.rollback()
        lease.heartbeat(now + timedelta(seconds=11))
        with Session(live_engine) as database:
            second = reserve_machine(database, "machine-one", now + timedelta(seconds=11))
            assert second != first
            release_reservation(database, "machine-one", first)
            database.commit()
            assert database.get(WorkerMachine, "machine-one").reservation_id == second
            release_reservation(database, "machine-one", second)
            database.commit()
            assert database.get(WorkerMachine, "machine-one").capture_state == "idle"
    finally:
        lease.release()


def test_absent_or_stale_worker_is_unavailable(live_engine) -> None:
    now = datetime.now(UTC)
    with Session(live_engine) as database:
        with pytest.raises(LiveMachineError, match="worker_unavailable"):
            reserve_machine(database, "machine-one", now)
        database.rollback()
    lease = MachineLease(live_engine, "machine-one", "worker-one")
    assert lease.acquire(now)
    try:
        with Session(live_engine) as database:
            with pytest.raises(LiveMachineError, match="worker_unavailable"):
                reserve_machine(database, "machine-one", now + timedelta(seconds=6))
            database.rollback()
    finally:
        lease.release()


def test_heartbeat_cannot_advertise_a_lost_advisory_lock(live_engine) -> None:
    now = datetime.now(UTC)
    lease = MachineLease(live_engine, "machine-one", "worker-one")
    assert lease.acquire(now)
    try:
        lease._connection.execute(text("SELECT pg_advisory_unlock_all()"))
        lease._connection.commit()
        with pytest.raises(LiveMachineError, match="worker_owner_lost"):
            lease.heartbeat(now)
    finally:
        lease.release()


def _target_jobs(engine):
    with Session(engine) as database, database.begin():
        camera = Camera(name="Affinity", name_key="affinity")
        database.add(camera)
        database.flush()
        session = FlowSession(
            name="Affinity",
            camera_id="affinity",
            registered_camera_id=camera.id,
            source_kind=SourceKind.SYNTHETIC,
        )
        database.add(session)
        database.flush()
        jobs = [
            ProcessingJob(
                session_id=session.id,
                kind=JobKind.SYNTHETIC_BASE_FLOW,
                status=JobStatus.PENDING,
                target_machine_id=machine,
            )
            for machine in ("machine-one", "machine-two", "machine-one")
        ]
        database.add_all(jobs)
        database.flush()
        return [job.id for job in jobs]


def test_claim_respects_machine_and_single_active_job(live_engine) -> None:
    ids = _target_jobs(live_engine)
    now = datetime.now(UTC)
    with Session(live_engine) as database:
        first = claim_next_job(database, "worker-one", now, machine_id="machine-one")
        assert first.id in (ids[0], ids[2])
        database.commit()
        assert claim_next_job(database, "worker-one", now, machine_id="machine-one") is None
        other = claim_next_job(database, "worker-two", now, machine_id="machine-two")
        assert other.id == ids[1]
        database.commit()


def test_recovery_never_fails_another_machines_job(live_engine) -> None:
    ids = _target_jobs(live_engine)
    now = datetime.now(UTC)
    with Session(live_engine) as database:
        claim_next_job(database, "worker-one", now, machine_id="machine-one")
        claim_next_job(database, "worker-two", now, machine_id="machine-two")
        database.commit()
        count = recover_interrupted_jobs(
            database, now, machine_id="machine-one", worker_id="worker-one"
        )
        assert count == 1
        database.commit()
        assert database.get(ProcessingJob, ids[1]).status == JobStatus.PROCESSING
