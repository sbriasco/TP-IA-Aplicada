"""Preview snapshot replace must not abort analysis on Windows file locks."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from flowsight.preview.broker import PreviewUpdate
from flowsight.preview.snapshot import write_preview_snapshot


def _update() -> PreviewUpdate:
    return PreviewUpdate(
        session_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        job_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        frame_index=3,
        video_timestamp_seconds=Decimal("0.12"),
        progress_percent=10.0,
        image_base64="abc",
        schema_version="2",
        measures=(),
    )


def test_replace_retries_after_windows_access_denied(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    attempts = {"n": 0}
    real_replace = Path.replace

    def flaky_replace(self: Path, target: Path) -> Path:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise PermissionError(5, "Acceso denegado")
        return real_replace(self, target)

    with patch("pathlib.Path.replace", flaky_replace):
        with patch("flowsight.preview.snapshot.time.sleep", lambda _s: None):
            write_preview_snapshot(path, _update())

    assert path.is_file()
    assert attempts["n"] == 3


def test_replace_gives_up_without_raising(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"

    def always_locked(self: Path, target: Path) -> Path:
        del self, target
        raise PermissionError(5, "Acceso denegado")

    with patch("pathlib.Path.replace", always_locked):
        with patch("flowsight.preview.snapshot.time.sleep", lambda _s: None):
            write_preview_snapshot(path, _update())

    assert not path.exists()
