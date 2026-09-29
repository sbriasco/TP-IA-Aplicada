from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

import pytest
from pydantic import SecretStr

from flowsight.api import main
from flowsight.api.main import prepare_videos_dir
from flowsight.core.config import Settings


@pytest.fixture(autouse=True)
def enabled_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    # Alembic's `fileConfig` disables existing loggers when other tests migrate
    # in this same process; the API never runs migrations in-process.
    monkeypatch.setattr(main.logger, "disabled", False)


def _settings(videos_dir: Path | None) -> Settings:
    return Settings.model_construct(
        database_url=SecretStr("postgresql+psycopg://u:p@127.0.0.1:5433/db"),
        videos_dir=videos_dir,
    )


def _partial(incoming: Path, age_seconds: float) -> Path:
    path = incoming / f"{uuid.uuid4()}.partial"
    path.write_bytes(b"parcial")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_removes_stale_partials_on_startup(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    incoming = tmp_path / ".incoming"
    incoming.mkdir()
    stale = _partial(incoming, 2 * 3600)
    recent = _partial(incoming, 60)

    with caplog.at_level(logging.WARNING):
        prepare_videos_dir(_settings(tmp_path))

    assert not stale.exists()
    assert recent.exists()
    assert caplog.records == []


def test_warns_and_continues_without_videos_dir(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        prepare_videos_dir(_settings(None))

    assert len(caplog.records) == 1
    assert "FLOWSIGHT_VIDEOS_DIR" in caplog.text


def test_warns_without_absolute_path_when_folder_is_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "no-existe"

    with caplog.at_level(logging.WARNING):
        prepare_videos_dir(_settings(missing))

    assert len(caplog.records) == 1
    assert "FLOWSIGHT_VIDEOS_DIR" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert not missing.exists()


def test_warns_without_absolute_path_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(videos_dir: Path, max_age: float = 3600) -> int:
        raise PermissionError(13, "Permission denied", str(videos_dir / ".incoming" / "x"))

    monkeypatch.setattr(main, "cleanup_stale_partials", fail)

    with caplog.at_level(logging.WARNING):
        prepare_videos_dir(_settings(tmp_path))

    assert len(caplog.records) == 1
    assert str(tmp_path) not in caplog.text
