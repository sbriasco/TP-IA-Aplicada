"""Shared local API/worker credentials, generated without manual environment setup."""

from __future__ import annotations

import json
import secrets
import time
import uuid
from pathlib import Path

from pydantic import SecretStr

from flowsight.core.config import ConfigurationError, Settings


def configure_local_webcam(settings: Settings, *, directory: Path | None = None) -> Settings:
    if settings.machine_id and settings.live_channel_token is not None:
        return settings
    directory = directory or Path(__file__).resolve().parents[4] / ".tools" / "runtime"
    path = directory / "webcam.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for _ in range(100):
            try:
                with path.open("x", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "machine_id": "local-" + uuid.uuid4().hex,
                            "token": secrets.token_urlsafe(32),
                        },
                        handle,
                    )
            except FileExistsError:
                pass
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Another process may still be completing its first write.
                time.sleep(0.02)
                continue
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("machine_id"), str)
                or not isinstance(value.get("token"), str)
                or len(value["token"]) < 32
            ):
                break
            return settings.model_copy(
                update={
                    "machine_id": settings.machine_id or value["machine_id"],
                    "live_channel_token": settings.live_channel_token or SecretStr(value["token"]),
                }
            )
    except OSError:
        pass
    raise ConfigurationError(
        "No se pudo inicializar la conexión local de webcam. "
        "Revisá los permisos de la carpeta del proyecto y reiniciá la app."
    )
