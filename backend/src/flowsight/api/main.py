"""FlowSight HTTP API bootstrap."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from flowsight.api.routes import router
from flowsight.core.config import ConfigurationError, Settings, load_settings
from flowsight.db.session import create_database_engine, create_session_factory
from flowsight.preview.broker import PreviewBroker
from flowsight.video.storage import StorageError, cleanup_stale_partials, ensure_videos_dir

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Validate configuration before exposing an application instance."""

    settings: Settings = load_settings()
    application = FastAPI(title="FlowSight API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.settings = settings
    application.state.engine = create_database_engine(settings)
    try:
        with application.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        application.state.engine.dispose()
        raise ConfigurationError(
            "PostgreSQL no está disponible. Iniciá el servicio y revisá FLOWSIGHT_DATABASE_URL."
        ) from None
    application.state.session_factory = create_session_factory(application.state.engine)
    prepare_videos_dir(settings)
    application.state.preview_broker = PreviewBroker()
    if os.environ.get("FLOWSIGHT_CHAT_FAKE_DRAFTER") == "1":
        from flowsight.services.chat import suite_drafter

        application.state.chat_drafter = suite_drafter
    application.include_router(router)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_request, _error) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "La solicitud no cumple el contrato.",
            },
        )

    return application


def prepare_videos_dir(settings: Settings) -> None:
    """Delete stale partial uploads; never block startup over the videos folder."""

    # Warnings name the variable, never the path (FR-013).
    try:
        videos_dir = ensure_videos_dir(settings)
    except StorageError as error:
        if error.code == "videos_dir_not_configured":
            logger.warning(
                "FLOWSIGHT_VIDEOS_DIR no está configurada: registrar videos responderá 503."
            )
        else:
            logger.warning(
                "FLOWSIGHT_VIDEOS_DIR no existe o no se puede escribir: "
                "registrar videos responderá 503."
            )
        return
    try:
        cleanup_stale_partials(videos_dir)
    except OSError as error:
        logger.warning(
            "No se pudieron borrar subidas incompletas en FLOWSIGHT_VIDEOS_DIR (%s).",
            type(error).__name__,
        )


app = create_app
