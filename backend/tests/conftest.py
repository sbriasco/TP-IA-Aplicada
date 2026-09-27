"""Shared test helpers.

`destructive_database_url()` guards every test that downgrades, truncates or
inserts test data: it never returns the team's shared Azure database.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
AZURE_HOST_SUFFIX = ".postgres.database.azure.com"
_HOW_TO_FIX = (
    "Configurá FLOWSIGHT_TEST_DATABASE_URL con un PostgreSQL local o de pruebas "
    "(ver .env.example)."
)


def destructive_database_url(
    environ: Mapping[str, str] | None = None,
    dotenv: Mapping[str, str | None] | None = None,
) -> str:
    """Return the database URL destructive tests may use, or fail without echoing it."""

    if environ is None:
        environ = os.environ
    if dotenv is None:
        dotenv = dotenv_values(ROOT_DIR / ".env")

    test_url = _setting("FLOWSIGHT_TEST_DATABASE_URL", environ, dotenv)
    if test_url is not None:
        if _is_azure(_host(test_url, "FLOWSIGHT_TEST_DATABASE_URL")):
            pytest.fail(
                "FLOWSIGHT_TEST_DATABASE_URL apunta a la base compartida de Azure; las "
                "pruebas destructivas nunca corren ahí. " + _HOW_TO_FIX,
                pytrace=False,
            )
        return test_url

    database_url = _setting("FLOWSIGHT_DATABASE_URL", environ, dotenv)
    if database_url is None:
        pytest.fail(
            "No hay base de datos para las pruebas PostgreSQL. " + _HOW_TO_FIX, pytrace=False
        )
    host = _host(database_url, "FLOWSIGHT_DATABASE_URL")
    if _is_azure(host):
        pytest.fail(
            "FLOWSIGHT_DATABASE_URL apunta a la base compartida de Azure; las pruebas "
            "destructivas nunca corren ahí. " + _HOW_TO_FIX,
            pytrace=False,
        )
    if host not in LOCAL_HOSTS:
        pytest.fail(
            "FLOWSIGHT_DATABASE_URL no apunta a localhost, 127.0.0.1 ni ::1. " + _HOW_TO_FIX,
            pytrace=False,
        )
    return database_url


def _setting(
    name: str, environ: Mapping[str, str], dotenv: Mapping[str, str | None]
) -> str | None:
    value = environ.get(name)
    if value is None:
        value = dotenv.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _host(url: str, variable: str) -> str:
    try:
        host = make_url(url).host
    except ArgumentError:
        host = None
    if not host:
        pytest.fail(f"{variable} no tiene un host válido. " + _HOW_TO_FIX, pytrace=False)
    return host.lower().rstrip(".")


def _is_azure(host: str) -> bool:
    return host.endswith(AZURE_HOST_SUFFIX)
