"""Shared API error format and redaction of sensitive text (FR-013)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from flowsight.core.config import Settings

VIDEOS_DIR_MARKER = "<FLOWSIGHT_VIDEOS_DIR>"
DATABASE_URL_MARKER = "<FLOWSIGHT_DATABASE_URL>"
PATH_MARKER = "<ruta>"

# Quoted paths (as in OSError messages) may contain spaces; unquoted ones end at
# whitespace. Lookbehinds keep URLs, fractions and relative paths untouched.
_QUOTED_PATH = re.compile(r"""(['"])(?:[A-Za-z]:[\\/]|\\\\|/)[^'"\n]*\1""")
_WINDOWS_PATH = re.compile(r"""(?<!\w)[A-Za-z]:[\\/][^\s'"<>|]*""")
_UNC_PATH = re.compile(r"""(?<![\w\\])\\\\[^\s'"<>|]+""")
_POSIX_PATH = re.compile(r"""(?<![\w.:/~>\\-])/[^\s'"<>|]+""")


def api_error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    """Build an `HTTPException` whose body is `{"detail": {"code", "message", ...}}`."""

    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message, **extra}
    )


def redact_paths(text: str, settings: Settings) -> str:
    """Replace the database URL, the videos folder and any absolute path with markers."""

    database_url = getattr(settings, "database_url", None)
    if database_url is not None:
        text = _redact_database_url(text, database_url.get_secret_value())

    videos_dir = getattr(settings, "videos_dir", None)
    if videos_dir is not None:
        for spelling in {str(videos_dir), videos_dir.as_posix()}:
            boundary = re.escape(spelling.rstrip("\\/")) + r"(?=[\\/\s'\"]|$)"
            text = re.sub(boundary, VIDEOS_DIR_MARKER, text)

    text = _QUOTED_PATH.sub(lambda match: f"{match[1]}{PATH_MARKER}{match[1]}", text)
    text = _WINDOWS_PATH.sub(PATH_MARKER, text)
    text = _UNC_PATH.sub(PATH_MARKER, text)
    return _POSIX_PATH.sub(PATH_MARKER, text)


def _redact_database_url(text: str, database_url: str) -> str:
    if not database_url:
        return text
    text = text.replace(database_url, DATABASE_URL_MARKER)
    try:
        password = make_url(database_url).password
    except ArgumentError:
        password = None
    if password:
        text = text.replace(str(password), "<redactado>")
    return text
