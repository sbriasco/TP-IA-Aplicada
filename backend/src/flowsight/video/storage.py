"""Local video folder: streamed copy with SHA-256, atomic finalize and availability.

The server names every stored file (`<session_id><ext>`), so client filenames
never reach a path (R2). Availability is computed on demand per machine (R7).
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Literal

from starlette.requests import ClientDisconnect

from flowsight.core.config import Settings

CHUNK_SIZE = 1024 * 1024
INCOMING_DIR = ".incoming"
PARTIAL_SUFFIX = ".partial"
ALLOWED_EXTENSIONS = frozenset({".mp4", ".mpg", ".mpeg", ".avi", ".mov", ".mkv"})

StorageErrorCode = Literal[
    "file_empty",
    "unsupported_format",
    "upload_interrupted",
    "insufficient_storage",
    "videos_dir_not_configured",
    "videos_dir_not_writable",
]
Availability = Literal["available", "missing", "mismatch", "not_configured"]


class StorageError(RuntimeError):
    """The upload or the videos folder failed; `code` is the API error code."""

    def __init__(self, code: StorageErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PartialUpload:
    path: Path
    sha256: str
    size_bytes: int


def ensure_videos_dir(settings: Settings) -> Path:
    """Return the configured videos folder with `.incoming/` ready, or raise."""

    videos_dir = settings.videos_dir
    if videos_dir is None:
        raise StorageError("videos_dir_not_configured")
    if not videos_dir.is_dir():
        raise StorageError("videos_dir_not_writable")
    incoming = videos_dir / INCOMING_DIR
    try:
        incoming.mkdir(exist_ok=True)
    except OSError:
        raise StorageError("videos_dir_not_writable") from None
    if not all(os.access(path, os.W_OK | os.X_OK) for path in (videos_dir, incoming)):
        raise StorageError("videos_dir_not_writable")
    return videos_dir


def extension_for(filename: str) -> str:
    """Lower-case allowed extension of the client's filename, or `unsupported_format`."""

    extension = os.path.splitext(PureWindowsPath(filename).name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise StorageError("unsupported_format")
    return extension


def video_path(videos_dir: Path, relative_path: str) -> Path:
    """Resolve a stored `relative_path` inside `videos_dir`, refusing anything outside."""

    parts = relative_path.replace("\\", "/").split("/")
    if (
        not relative_path
        or relative_path[0] in "/\\"
        or PureWindowsPath(relative_path).drive
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ValueError("relative_path must stay inside the videos folder")
    return videos_dir / relative_path


async def stream_to_partial(chunks: AsyncIterator[bytes], videos_dir: Path) -> PartialUpload:
    """Copy the body to `.incoming/<uuid>.partial`, hashing it in the same pass."""

    incoming = videos_dir / INCOMING_DIR
    try:
        incoming.mkdir(exist_ok=True)
    except OSError:
        raise StorageError("videos_dir_not_writable") from None
    path = incoming / f"{uuid.uuid4()}{PARTIAL_SUFFIX}"
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as partial:
            pending = bytearray()
            async for chunk in chunks:
                digest.update(chunk)
                size += len(chunk)
                pending += chunk
                while len(pending) >= CHUNK_SIZE:
                    block = bytes(pending[:CHUNK_SIZE])
                    del pending[:CHUNK_SIZE]
                    await asyncio.to_thread(partial.write, block)
            await asyncio.to_thread(_write_and_sync, partial, bytes(pending))
    except ClientDisconnect:
        path.unlink(missing_ok=True)
        raise StorageError("upload_interrupted") from None
    except OSError as error:
        path.unlink(missing_ok=True)
        if error.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
            raise StorageError("insufficient_storage") from None
        raise
    except BaseException:
        path.unlink(missing_ok=True)
        raise

    if size == 0:
        path.unlink(missing_ok=True)
        raise StorageError("file_empty")
    return PartialUpload(path=path, sha256=digest.hexdigest(), size_bytes=size)


def _write_and_sync(partial: BinaryIO, block: bytes) -> None:
    partial.write(block)
    partial.flush()
    os.fsync(partial.fileno())


def finalize(
    partial: PartialUpload, videos_dir: Path, session_id: uuid.UUID | str, extension: str
) -> str:
    """Atomically move the partial to `<session_id><ext>` and return that relative path."""

    if extension not in ALLOWED_EXTENSIONS:
        raise StorageError("unsupported_format")
    relative_path = f"{session_id}{extension}"
    os.replace(partial.path, video_path(videos_dir, relative_path))
    return relative_path


def discard(partial: PartialUpload, videos_dir: Path, relative_path: str | None = None) -> None:
    """Remove the partial and, if already finalized, its destination."""

    partial.path.unlink(missing_ok=True)
    if relative_path is not None:
        video_path(videos_dir, relative_path).unlink(missing_ok=True)


def cleanup_stale_partials(videos_dir: Path, max_age: float = 3600) -> int:
    """Delete `.partial` files older than `max_age` seconds; return how many."""

    incoming = videos_dir / INCOMING_DIR
    if not incoming.is_dir():
        return 0
    cutoff = time.time() - max_age
    removed = 0
    for path in incoming.glob(f"*{PARTIAL_SUFFIX}"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed


# Per-process cache of local hashes: path -> (size, mtime_ns, sha256).
_hash_cache: dict[str, tuple[int, int, str]] = {}
_hash_cache_lock = threading.Lock()


def check_availability(
    videos_dir: Path | None, relative_path: str, size_bytes: int, sha256: str
) -> Availability:
    """Compare the local file with the registered size and SHA-256 (FR-009)."""

    if videos_dir is None:
        return "not_configured"
    path = video_path(videos_dir, relative_path)
    try:
        stat = path.stat()
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    if not path.is_file():
        return "missing"
    if stat.st_size != size_bytes:
        return "mismatch"
    return "available" if _cached_sha256(path, stat) == sha256 else "mismatch"


def _cached_sha256(path: Path, stat: os.stat_result) -> str:
    key = str(path)
    with _hash_cache_lock:
        cached = _hash_cache.get(key)
    if cached is not None and cached[:2] == (stat.st_size, stat.st_mtime_ns):
        return cached[2]
    digest = hashlib.sha256()
    with path.open("rb") as video:
        while block := video.read(CHUNK_SIZE):
            digest.update(block)
    with _hash_cache_lock:
        _hash_cache[key] = (stat.st_size, stat.st_mtime_ns, digest.hexdigest())
    return digest.hexdigest()
