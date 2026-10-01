"""Validated local configuration shared by the API and worker."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MACHINE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{2,39}")


class ConfigurationError(RuntimeError):
    """Configuration is missing or invalid and the process must not start."""


class Settings(BaseSettings):
    """FlowSight settings loaded from environment variables or a local `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test"] = Field(validation_alias="FLOWSIGHT_ENV")
    database_url: SecretStr = Field(validation_alias="FLOWSIGHT_DATABASE_URL", min_length=1)
    api_host: str = Field(default="127.0.0.1", validation_alias="FLOWSIGHT_API_HOST", min_length=1)
    api_port: int = Field(default=8000, validation_alias="FLOWSIGHT_API_PORT", ge=1, le=65535)
    worker_id: str = Field(validation_alias="FLOWSIGHT_WORKER_ID", min_length=1)
    preview_max_fps: int = Field(
        default=5, validation_alias="FLOWSIGHT_PREVIEW_MAX_FPS", gt=0, le=5
    )
    # Optional per-machine settings: the API and worker start without them, and
    # the video endpoints report them as not configured.
    videos_dir: Path | None = Field(default=None, validation_alias="FLOWSIGHT_VIDEOS_DIR")
    machine_id: str | None = Field(default=None, validation_alias="FLOWSIGHT_MACHINE_ID")
    # Tests and CI stay on the fake detector. A bad value must not block startup.
    detector: Literal["fake", "ultralytics"] = Field(
        default="fake", validation_alias="FLOWSIGHT_DETECTOR"
    )
    yolo_weights: Path | None = Field(default=None, validation_alias="FLOWSIGHT_YOLO_WEIGHTS")
    # The API starts without Azure. This only bounds one chat question.
    chat_timeout_seconds: float = Field(
        default=20, validation_alias="FLOWSIGHT_CHAT_TIMEOUT_SECONDS", gt=0, le=120
    )

    @field_validator("videos_dir", mode="before")
    @classmethod
    def validate_videos_dir(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        if value is not None and not Path(value).is_absolute():
            raise ValueError("must be an absolute path")
        return value

    @field_validator("detector", mode="before")
    @classmethod
    def validate_detector(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            return "fake"
        normalized = value.strip().lower()
        return normalized if normalized in {"fake", "ultralytics"} else "fake"

    @field_validator("yolo_weights", mode="before")
    @classmethod
    def validate_yolo_weights(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return value

    @field_validator("machine_id", mode="before")
    @classmethod
    def validate_machine_id(cls, value: object) -> str | None:
        # An invalid id must not block startup; it is exposed as not configured.
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value if MACHINE_ID_PATTERN.fullmatch(value) else None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("must be a PostgreSQL URL")
        return value

    @field_validator("api_host", "worker_id")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


def load_settings() -> Settings:
    """Load settings or raise a safe, actionable error without echoing values."""

    try:
        return Settings()
    except ValidationError as error:
        problems = []
        for detail in error.errors(include_input=False, include_url=False):
            variable = str(detail["loc"][0])
            error_type = str(detail["type"])
            cause = _cause_for(error_type, str(detail["msg"]))
            problems.append(
                f"{variable}: {cause}. Corregí la variable usando .env.example como referencia."
            )
        raise ConfigurationError("Configuración inválida: " + " ".join(problems)) from None


def _cause_for(error_type: str, message: str) -> str:
    if error_type == "missing":
        return "missing"
    if error_type == "string_too_short" or "must not be empty" in message:
        return "empty"
    return "invalid_format"
