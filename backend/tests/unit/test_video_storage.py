from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import time
import uuid
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

import pytest
from pydantic import SecretStr
from starlette.requests import ClientDisconnect

from flowsight.core.config import Settings
from flowsight.video import storage
from flowsight.video.storage import (
    ALLOWED_EXTENSIONS,
    CHUNK_SIZE,
    PartialUpload,
    StorageError,
    check_availability,
    cleanup_stale_partials,
    discard,
    ensure_videos_dir,
    extension_for,
    finalize,
    stream_to_partial,
    video_path,
)

MIB = 1024 * 1024


async def _chunks(parts: Iterable[bytes]) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def _disconnect_after(parts: Iterable[bytes]) -> AsyncIterator[bytes]:
    for part in parts:
        yield part
    raise ClientDisconnect()


def _stream(videos_dir: Path, chunks: AsyncIterator[bytes]) -> PartialUpload:
    return asyncio.run(stream_to_partial(chunks, videos_dir))


def _incoming(videos_dir: Path) -> list[Path]:
    incoming = videos_dir / ".incoming"
    return sorted(incoming.iterdir()) if incoming.exists() else []


def _settings(videos_dir: Path | None) -> Settings:
    return Settings.model_construct(
        database_url=SecretStr("postgresql+psycopg://u:p@127.0.0.1:5433/db"),
        videos_dir=videos_dir,
    )


@pytest.fixture
def videos_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "videos"
    directory.mkdir()
    return directory


def test_chunk_size_is_one_mebibyte() -> None:
    assert CHUNK_SIZE == MIB


def test_stream_copies_to_incoming_partial_hashing_in_one_pass(videos_dir: Path) -> None:
    # Irregular chunk sizes, larger than one block in total.
    parts = [b"a" * 700_000, b"b" * (MIB + MIB // 2), b"c"]
    body = b"".join(parts)

    partial = _stream(videos_dir, _chunks(parts))

    assert partial.path.parent == videos_dir / ".incoming"
    assert partial.path.suffix == ".partial"
    uuid.UUID(partial.path.stem)
    assert partial.path.read_bytes() == body
    assert partial.size_bytes == len(body)
    assert partial.sha256 == hashlib.sha256(body).hexdigest()
    assert partial.sha256 == partial.sha256.lower()


def test_stream_rejects_empty_body_without_leaving_partial(videos_dir: Path) -> None:
    with pytest.raises(StorageError) as excinfo:
        _stream(videos_dir, _chunks([]))

    assert excinfo.value.code == "file_empty"
    assert _incoming(videos_dir) == []


def test_stream_removes_partial_when_client_disconnects(videos_dir: Path) -> None:
    with pytest.raises(StorageError) as excinfo:
        _stream(videos_dir, _disconnect_after([b"x" * (2 * MIB)]))

    assert excinfo.value.code == "upload_interrupted"
    assert _incoming(videos_dir) == []


def test_stream_reports_insufficient_storage_without_leaving_partial(
    monkeypatch: pytest.MonkeyPatch, videos_dir: Path
) -> None:
    def disk_full(fd: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(storage.os, "fsync", disk_full)

    with pytest.raises(StorageError) as excinfo:
        _stream(videos_dir, _chunks([b"x" * 1024]))

    assert excinfo.value.code == "insufficient_storage"
    assert _incoming(videos_dir) == []


def test_finalize_moves_partial_to_session_name(videos_dir: Path) -> None:
    partial = _stream(videos_dir, _chunks([b"video"]))
    session_id = uuid.uuid4()

    relative_path = finalize(partial, videos_dir, session_id, ".mp4")

    assert relative_path == f"{session_id}.mp4"
    assert (videos_dir / relative_path).read_bytes() == b"video"
    assert not partial.path.exists()


def test_discard_removes_partial_and_destination(videos_dir: Path) -> None:
    pending = _stream(videos_dir, _chunks([b"pendiente"]))
    discard(pending, videos_dir)
    assert not pending.path.exists()

    moved = _stream(videos_dir, _chunks([b"movido"]))
    relative_path = finalize(moved, videos_dir, uuid.uuid4(), ".avi")
    discard(moved, videos_dir, relative_path)

    assert not (videos_dir / relative_path).exists()
    assert _incoming(videos_dir) == []


def test_cleanup_removes_only_stale_partials(videos_dir: Path) -> None:
    incoming = videos_dir / ".incoming"
    incoming.mkdir()
    stale = incoming / f"{uuid.uuid4()}.partial"
    recent = incoming / f"{uuid.uuid4()}.partial"
    stale.write_bytes(b"viejo")
    recent.write_bytes(b"nuevo")
    two_hours_ago = time.time() - 2 * 3600
    os.utime(stale, (two_hours_ago, two_hours_ago))
    registered = videos_dir / f"{uuid.uuid4()}.mp4"
    registered.write_bytes(b"registrado")
    os.utime(registered, (two_hours_ago, two_hours_ago))

    cleanup_stale_partials(videos_dir, max_age=3600)

    assert not stale.exists()
    assert recent.exists()
    assert registered.exists()


def test_cleanup_tolerates_missing_incoming_dir(videos_dir: Path) -> None:
    cleanup_stale_partials(videos_dir, max_age=3600)


def test_allowed_extensions_are_exactly_the_contract_ones() -> None:
    assert set(ALLOWED_EXTENSIONS) == {".mp4", ".mpg", ".mpeg", ".avi", ".mov", ".mkv"}


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("clip.mp4", ".mp4"),
        ("CLIP.MP4", ".mp4"),
        ("toma.Mpeg", ".mpeg"),
        ("a.b.mkv", ".mkv"),
        ("cam.MOV", ".mov"),
    ],
)
def test_extension_for_accepts_allowed_extensions_case_insensitively(
    filename: str, expected: str
) -> None:
    assert extension_for(filename) == expected


@pytest.mark.parametrize("filename", ["clip.webm", "clip.mp4.txt", "clip", "mp4", ".mp4x"])
def test_extension_for_rejects_other_extensions(filename: str) -> None:
    with pytest.raises(StorageError) as excinfo:
        extension_for(filename)

    assert excinfo.value.code == "unsupported_format"


def test_video_path_resolves_inside_videos_dir(videos_dir: Path) -> None:
    session_id = uuid.uuid4()

    assert video_path(videos_dir, f"{session_id}.mp4") == videos_dir / f"{session_id}.mp4"


@pytest.mark.parametrize(
    "relative_path",
    ["../fuera.mp4", "sub/../../fuera.mp4", "/etc/fuera.mp4", "\\fuera.mp4", ""],
)
def test_video_path_rejects_unsafe_relative_paths(videos_dir: Path, relative_path: str) -> None:
    with pytest.raises(ValueError):
        video_path(videos_dir, relative_path)


def _register(videos_dir: Path, content: bytes) -> tuple[str, int, str]:
    relative_path = f"{uuid.uuid4()}.mp4"
    (videos_dir / relative_path).write_bytes(content)
    return relative_path, len(content), hashlib.sha256(content).hexdigest()


def test_availability_available_when_size_and_hash_match(videos_dir: Path) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")

    assert check_availability(videos_dir, relative_path, size, sha256) == "available"


def test_availability_missing_when_file_does_not_exist(videos_dir: Path) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")
    (videos_dir / relative_path).unlink()

    assert check_availability(videos_dir, relative_path, size, sha256) == "missing"


def test_availability_mismatch_when_size_differs(videos_dir: Path) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")
    (videos_dir / relative_path).write_bytes(b"otro contenido mas largo")

    assert check_availability(videos_dir, relative_path, size, sha256) == "mismatch"


def test_availability_mismatch_when_same_size_but_different_content(videos_dir: Path) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")
    (videos_dir / relative_path).write_bytes(b"CONTENIDO ORIGINAL")

    assert check_availability(videos_dir, relative_path, size, sha256) == "mismatch"


def test_availability_not_configured_without_videos_dir(videos_dir: Path) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")

    assert check_availability(None, relative_path, size, sha256) == "not_configured"


def test_availability_cache_skips_rehash_while_path_size_and_mtime_are_unchanged(
    videos_dir: Path,
) -> None:
    relative_path, size, sha256 = _register(videos_dir, b"contenido original")
    path = videos_dir / relative_path
    assert check_availability(videos_dir, relative_path, size, sha256) == "available"

    # Same size and mtime_ns: the cached hash is reused, so the change goes unnoticed.
    stat = path.stat()
    path.write_bytes(b"CONTENIDO ORIGINAL")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert check_availability(videos_dir, relative_path, size, sha256) == "available"

    # A new mtime invalidates the entry and the file is hashed again.
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert check_availability(videos_dir, relative_path, size, sha256) == "mismatch"


def test_ensure_videos_dir_creates_incoming_and_returns_path(videos_dir: Path) -> None:
    assert ensure_videos_dir(_settings(videos_dir)) == videos_dir
    assert (videos_dir / ".incoming").is_dir()


def test_ensure_videos_dir_requires_configuration() -> None:
    with pytest.raises(StorageError) as excinfo:
        ensure_videos_dir(_settings(None))

    assert excinfo.value.code == "videos_dir_not_configured"


def test_ensure_videos_dir_rejects_missing_folder(tmp_path: Path) -> None:
    missing = tmp_path / "no-existe"

    with pytest.raises(StorageError) as excinfo:
        ensure_videos_dir(_settings(missing))

    assert excinfo.value.code == "videos_dir_not_writable"
    assert not missing.exists()


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="los permisos POSIX no restringen a root y no aplican en Windows",
)
def test_ensure_videos_dir_rejects_read_only_folder(videos_dir: Path) -> None:
    videos_dir.chmod(0o500)
    try:
        with pytest.raises(StorageError) as excinfo:
            ensure_videos_dir(_settings(videos_dir))
    finally:
        videos_dir.chmod(0o700)

    assert excinfo.value.code == "videos_dir_not_writable"
