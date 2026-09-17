"""Versioned synthetic preview image validation."""

from __future__ import annotations

import base64
from pathlib import Path

MAX_PREVIEW_BYTES = 100 * 1024


def load_preview_base64(path: Path) -> str:
    content = path.read_bytes()
    if len(content) > MAX_PREVIEW_BYTES:
        raise ValueError("La preview supera 100 KiB.")
    if jpeg_dimensions(content) != (320, 180):
        raise ValueError("La preview debe ser JPEG de 320×180.")
    return base64.b64encode(content).decode("ascii")


def jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    if not content.startswith(b"\xff\xd8"):
        return None
    offset = 2
    while offset + 9 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        marker = content[offset + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            height = int.from_bytes(content[offset + 5 : offset + 7], "big")
            width = int.from_bytes(content[offset + 7 : offset + 9], "big")
            return width, height
        if marker in {0xD8, 0xD9}:
            offset += 2
            continue
        length = int.from_bytes(content[offset + 2 : offset + 4], "big")
        if length < 2:
            return None
        offset += 2 + length
    return None
