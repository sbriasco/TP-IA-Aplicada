from __future__ import annotations

import pytest
from conftest import destructive_database_url

LOCAL_URL = "postgresql+psycopg://flowsight:local-secret@127.0.0.1:5432/flowsight"
AZURE_URL = (
    "postgresql+psycopg://flowsight:azure-secret@"
    "ia-aplicada-flowsight.postgres.database.azure.com:5432/postgres?sslmode=require"
)
REMOTE_URL = "postgresql+psycopg://flowsight:remote-secret@db.example.com:5432/flowsight"


def fail_message(environ: dict[str, str], dotenv: dict[str, str | None] | None = None) -> str:
    with pytest.raises(pytest.fail.Exception) as raised:
        destructive_database_url(environ=environ, dotenv=dotenv or {})
    return str(raised.value)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]", "LOCALHOST"])
def test_accepts_local_database_url(host: str) -> None:
    url = f"postgresql+psycopg://flowsight:secret@{host}:5432/flowsight"

    assert destructive_database_url(environ={"FLOWSIGHT_DATABASE_URL": url}, dotenv={}) == url


def test_prefers_test_database_url() -> None:
    environ = {"FLOWSIGHT_DATABASE_URL": AZURE_URL, "FLOWSIGHT_TEST_DATABASE_URL": LOCAL_URL}

    assert destructive_database_url(environ=environ, dotenv={}) == LOCAL_URL


def test_accepts_remote_test_database_url_that_is_not_azure() -> None:
    environ = {"FLOWSIGHT_TEST_DATABASE_URL": REMOTE_URL}

    assert destructive_database_url(environ=environ, dotenv={}) == REMOTE_URL


def test_reads_urls_from_dotenv_when_not_in_environment() -> None:
    dotenv = {"FLOWSIGHT_DATABASE_URL": AZURE_URL, "FLOWSIGHT_TEST_DATABASE_URL": LOCAL_URL}

    assert destructive_database_url(environ={}, dotenv=dotenv) == LOCAL_URL


def test_rejects_azure_database_url() -> None:
    message = fail_message({"FLOWSIGHT_DATABASE_URL": AZURE_URL})

    assert "FLOWSIGHT_TEST_DATABASE_URL" in message


def test_rejects_azure_even_as_test_database_url() -> None:
    mixed_case_url = AZURE_URL.replace("flowsight-", "FlowSight-")

    message = fail_message({"FLOWSIGHT_TEST_DATABASE_URL": mixed_case_url})

    assert "Azure" in message


def test_rejects_remote_host_without_test_database_url() -> None:
    message = fail_message({"FLOWSIGHT_DATABASE_URL": REMOTE_URL})

    assert "FLOWSIGHT_TEST_DATABASE_URL" in message


def test_rejects_missing_or_empty_configuration() -> None:
    message = fail_message({"FLOWSIGHT_TEST_DATABASE_URL": " "}, {"FLOWSIGHT_DATABASE_URL": ""})

    assert "FLOWSIGHT_TEST_DATABASE_URL" in message


def test_rejects_url_without_host() -> None:
    message = fail_message({"FLOWSIGHT_DATABASE_URL": "postgresql+psycopg:///flowsight?host=/tmp"})

    assert "FLOWSIGHT_TEST_DATABASE_URL" in message


@pytest.mark.parametrize(
    "environ",
    [
        {"FLOWSIGHT_DATABASE_URL": AZURE_URL},
        {"FLOWSIGHT_TEST_DATABASE_URL": AZURE_URL},
        {"FLOWSIGHT_DATABASE_URL": REMOTE_URL},
        {"FLOWSIGHT_DATABASE_URL": "not a url with password hunter2"},
    ],
)
def test_messages_never_expose_urls_or_passwords(environ: dict[str, str]) -> None:
    message = fail_message(environ)

    for url in environ.values():
        assert url not in message
    for secret in ("azure-secret", "remote-secret", "hunter2", "db.example.com"):
        assert secret not in message
    assert "ia-aplicada-flowsight" not in message
