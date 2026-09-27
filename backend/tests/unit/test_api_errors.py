from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from flowsight.api.errors import api_error, redact_paths
from flowsight.api.routes import not_found
from flowsight.core.config import Settings

DATABASE_URL = "postgresql+psycopg://flowsight:super-secret@db.internal:5432/flowsight"


def settings(videos_dir: Path | None = None) -> Settings:
    return Settings.model_construct(database_url=SecretStr(DATABASE_URL), videos_dir=videos_dir)


def test_api_error_matches_error_detail_contract() -> None:
    error = api_error(503, "videos_dir_not_configured", "Definí FLOWSIGHT_VIDEOS_DIR.")

    assert isinstance(error, HTTPException)
    assert error.status_code == 503
    assert error.detail == {
        "code": "videos_dir_not_configured",
        "message": "Definí FLOWSIGHT_VIDEOS_DIR.",
    }


def test_api_error_adds_extra_fields() -> None:
    error = api_error(409, "camera_exists", "Ya existe.", existing_id="abc")

    assert error.detail == {"code": "camera_exists", "message": "Ya existe.", "existing_id": "abc"}


@pytest.mark.parametrize("field", ["code", "message"])
def test_api_error_extra_fields_cannot_replace_code_or_message(field: str) -> None:
    with pytest.raises(TypeError):
        api_error(400, "x", "y", **{field: "z"})


def test_not_found_keeps_its_response_shape() -> None:
    error = not_found("Sesión inexistente.")

    assert error.status_code == 404
    assert error.detail == {"code": "not_found", "message": "Sesión inexistente."}


def test_redacts_videos_dir_keeping_relative_part(tmp_path: Path) -> None:
    videos_dir = tmp_path / "Videos de Santiago"
    text = f"No se pudo escribir {videos_dir / 'abc.mp4'}"

    redacted = redact_paths(text, settings(videos_dir))

    assert redacted == "No se pudo escribir <FLOWSIGHT_VIDEOS_DIR>/abc.mp4"
    assert "Santiago" not in redacted


def test_redacts_videos_dir_with_forward_slashes() -> None:
    videos_dir = Path("/srv/flowsight/videos")

    assert (
        redact_paths("falla en /srv/flowsight/videos", settings(videos_dir))
        == "falla en <FLOWSIGHT_VIDEOS_DIR>"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "[Errno 2] No such file or directory: '/home/santiago/Mis videos/a.mp4'",
            "[Errno 2] No such file or directory: '<ruta>'",
        ),
        ("falla en /home/santiago/a.mp4 al leer", "falla en <ruta> al leer"),
        (r"falla en C:\Users\santiago\a.mp4", "falla en <ruta>"),
        (r'abrió "C:\Users\Santiago Alvarez\a.mp4"', 'abrió "<ruta>"'),
        ("falla en D:/videos/a.mp4", "falla en <ruta>"),
        (r"share \\equipo-03\videos\a.mp4 caído", "share <ruta> caído"),
    ],
)
def test_redacts_any_absolute_path(text: str, expected: str) -> None:
    assert redact_paths(text, settings()) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Ver http://127.0.0.1:8000/sessions/abc para el detalle.",
        "Se procesaron 3/4 frames.",
        "El archivo videos/abc.mp4 es relativo.",
        "Convertir a MP4 o MPEG.",
    ],
)
def test_leaves_urls_fractions_and_relative_paths_untouched(text: str) -> None:
    assert redact_paths(text, settings()) == text


def test_redacts_database_url() -> None:
    redacted = redact_paths(f"conexión fallida: {DATABASE_URL}", settings())

    assert redacted == "conexión fallida: <FLOWSIGHT_DATABASE_URL>"
    assert "super-secret" not in redacted


def test_redacts_database_password_on_its_own() -> None:
    redacted = redact_paths('password "super-secret" rechazada', settings())

    assert "super-secret" not in redacted


def test_works_without_optional_settings() -> None:
    bare = Settings.model_construct()

    assert redact_paths("falla en /tmp/x.mp4", bare) == "falla en <ruta>"
