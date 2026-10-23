"""Database engine and session factory construction."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from flowsight.core.config import Settings

_AZURE_HOST_SUFFIX = ".postgres.database.azure.com"


def database_url_is_remote(database_url: str) -> bool:
    """True for non-loopback hosts (Azure Flexible Server and similar)."""

    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    return True


def database_url_is_azure(database_url: str) -> bool:
    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    host = (parsed.hostname or "").lower()
    return host.endswith(_AZURE_HOST_SUFFIX)


def engine_connect_args(database_url: str) -> dict[str, object]:
    """Short timeouts locally; Azure needs headroom for SSL + RTT."""

    if database_url_is_remote(database_url):
        return {"connect_timeout": 10}
    return {"connect_timeout": 2}


def engine_pool_kwargs(database_url: str) -> dict[str, object]:
    if database_url_is_remote(database_url):
        return {
            "pool_pre_ping": True,
            "pool_timeout": 30,
            "pool_recycle": 300,
            "pool_size": 5,
            "max_overflow": 5,
        }
    return {
        "pool_pre_ping": True,
        "pool_timeout": 1,
    }


def live_write_timeouts_ms(database_url: str) -> tuple[int, int]:
    """(lock_timeout_ms, statement_timeout_ms) for live checkpoint writes."""

    if database_url_is_remote(database_url):
        # Spec 009 used 250/1000 for local; remote RTT alone is often >100 ms.
        return 2000, 8000
    return 250, 1000


def create_database_engine(settings: Settings) -> Engine:
    url = settings.database_url.get_secret_value()
    return create_engine(
        url,
        hide_parameters=True,
        connect_args=engine_connect_args(url),
        **engine_pool_kwargs(url),
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
