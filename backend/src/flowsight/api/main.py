"""FlowSight HTTP API bootstrap."""

from __future__ import annotations

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


def create_app() -> FastAPI:
    """Validate configuration before exposing an application instance."""

    settings: Settings = load_settings()
    application = FastAPI(title="FlowSight API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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
    application.state.preview_broker = PreviewBroker()
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


app = create_app
