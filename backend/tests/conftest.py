"""Shared test helpers.

`destructive_database_url()` guards every test that downgrades, truncates or
inserts test data: it never returns the team's shared Azure database.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
AZURE_HOST_SUFFIX = ".postgres.database.azure.com"
_HOW_TO_FIX = (
    "Configurá FLOWSIGHT_TEST_DATABASE_URL con un PostgreSQL local o de pruebas (ver .env.example)."
)


def destructive_database_url(
    environ: Mapping[str, str] | None = None,
    dotenv: Mapping[str, str | None] | None = None,
) -> str:
    """Return the database URL destructive tests may use, or fail without echoing it."""

    if environ is None:
        environ = os.environ
    if dotenv is None:
        dotenv = dotenv_values(ROOT_DIR / ".env")

    test_url = _setting("FLOWSIGHT_TEST_DATABASE_URL", environ, dotenv)
    if test_url is not None:
        if _is_azure(_host(test_url, "FLOWSIGHT_TEST_DATABASE_URL")):
            pytest.fail(
                "FLOWSIGHT_TEST_DATABASE_URL apunta a la base compartida de Azure; las "
                "pruebas destructivas nunca corren ahí. " + _HOW_TO_FIX,
                pytrace=False,
            )
        return test_url

    database_url = _setting("FLOWSIGHT_DATABASE_URL", environ, dotenv)
    if database_url is None:
        pytest.fail(
            "No hay base de datos para las pruebas PostgreSQL. " + _HOW_TO_FIX, pytrace=False
        )
    host = _host(database_url, "FLOWSIGHT_DATABASE_URL")
    if _is_azure(host):
        pytest.fail(
            "FLOWSIGHT_DATABASE_URL apunta a la base compartida de Azure; las pruebas "
            "destructivas nunca corren ahí. " + _HOW_TO_FIX,
            pytrace=False,
        )
    if host not in LOCAL_HOSTS:
        pytest.fail(
            "FLOWSIGHT_DATABASE_URL no apunta a localhost, 127.0.0.1 ni ::1. " + _HOW_TO_FIX,
            pytrace=False,
        )
    return database_url


def _setting(name: str, environ: Mapping[str, str], dotenv: Mapping[str, str | None]) -> str | None:
    value = environ.get(name)
    if value is None:
        value = dotenv.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _host(url: str, variable: str) -> str:
    try:
        host = make_url(url).host
    except ArgumentError:
        host = None
    if not host:
        pytest.fail(f"{variable} no tiene un host válido. " + _HOW_TO_FIX, pytrace=False)
    return host.lower().rstrip(".")


def _is_azure(host: str) -> bool:
    return host.endswith(AZURE_HOST_SUFFIX)


@pytest.fixture
def live_engine(monkeypatch: pytest.MonkeyPatch):
    """Dedicated live fixtures; every destructive operation follows the local guard."""
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    from alembic import command

    url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", url)
    config = Config(ROOT_DIR / "backend" / "alembic.ini")
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


@pytest.fixture
def live_job(live_engine):
    import uuid
    from datetime import UTC, datetime

    from sqlalchemy.orm import sessionmaker

    from flowsight.capture.contracts import CaptureProbeResult
    from flowsight.db.models import (
        Camera,
        EntryDirection,
        SceneEntryLine,
        SceneVersion,
        SceneVersionShop,
        Shop,
    )
    from flowsight.services.live_jobs import start_live_job
    from flowsight.services.live_sessions import LiveChecks, prepare_session
    from flowsight.worker.live_control import MachineLease

    factory = sessionmaker(live_engine, expire_on_commit=False)
    lease = MachineLease(live_engine, "expo-runner", "worker-runner")
    assert lease.acquire(datetime.now(UTC))
    checks = LiveChecks()
    with factory.begin() as db:
        camera = Camera(id=uuid.uuid4(), name="Runner", name_key="runner")
        db.add(camera)
        db.flush()
        session = prepare_session(
            db,
            name="Live",
            camera_id=camera.id,
            machine_id="expo-runner",
            label_mode="directions",
            probe=CaptureProbeResult(b"jpeg", 320, 180, "fake", 0),
            now=datetime.now(UTC),
        )
        version = SceneVersion(
            id=uuid.uuid4(),
            camera_id=camera.id,
            version_number=1,
            reference_session_id=session.id,
            frame_width=320,
            frame_height=180,
        )
        db.add(version)
        db.flush()
        shop = Shop(id=uuid.uuid4(), camera_id=camera.id)
        db.add(shop)
        db.flush()
        version_shop = SceneVersionShop(
            id=uuid.uuid4(),
            scene_version_id=version.id,
            shop_id=shop.id,
            camera_id=camera.id,
            position=0,
            name="Paso",
            name_key="paso",
        )
        db.add(version_shop)
        db.flush()
        db.add(
            SceneEntryLine(
                version_shop_id=version_shop.id,
                start_x=0.1,
                start_y=0.5,
                end_x=0.9,
                end_y=0.5,
                entry_direction=EntryDirection.A_TO_B,
            )
        )
        token = checks.issue(
            session_id=session.id,
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
            device_index=0,
            width=320,
            height=180,
        )
        job = start_live_job(
            db,
            session_id=session.id,
            machine_id="expo-runner",
            scene_version_id=version.id,
            checks=checks,
            check_token=token,
            frame_confirmed=True,
            now=datetime.now(UTC),
        )
        job_id = job.id
    yield factory, job_id, lease
    lease.release()
