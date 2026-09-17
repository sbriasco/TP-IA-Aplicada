from __future__ import annotations

import base64
from pathlib import Path

import pytest

from flowsight.preview.image import (
    MAX_PREVIEW_BYTES,
    jpeg_dimensions,
    load_preview_base64,
)

PREVIEW_PATH = (
    Path(__file__).resolve().parents[3] / "fixtures" / "synthetic" / "preview-320x180.jpg"
)


def test_versioned_preview_is_a_bounded_320_by_180_jpeg() -> None:
    content = PREVIEW_PATH.read_bytes()

    assert len(content) <= MAX_PREVIEW_BYTES
    assert jpeg_dimensions(content) == (320, 180)
    assert base64.b64decode(load_preview_base64(PREVIEW_PATH)) == content


def test_preview_rejects_oversized_content(tmp_path: Path) -> None:
    preview = tmp_path / "large.jpg"
    preview.write_bytes(b"\xff\xd8" + b"0" * MAX_PREVIEW_BYTES)

    with pytest.raises(ValueError, match="supera 100 KiB"):
        load_preview_base64(preview)
