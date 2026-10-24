"""Remote vs local engine and live-write timeout helpers."""

from flowsight.db.session import (
    database_url_is_azure,
    database_url_is_remote,
    engine_connect_args,
    engine_pool_kwargs,
    live_write_timeouts_ms,
)


def test_local_urls_keep_tight_timeouts() -> None:
    url = "postgresql+psycopg://flowsight:x@127.0.0.1:5432/flowsight"
    assert database_url_is_remote(url) is False
    assert database_url_is_azure(url) is False
    assert engine_connect_args(url) == {"connect_timeout": 2}
    assert engine_pool_kwargs(url) == {"pool_pre_ping": True, "pool_timeout": 1}
    assert live_write_timeouts_ms(url) == (250, 1000)


def test_azure_urls_get_remote_headroom() -> None:
    url = (
        "postgresql+psycopg://flowsight:x@ia-aplicada-flowsight.postgres.database.azure.com:5432/"
        "postgres?sslmode=require"
    )
    assert database_url_is_remote(url) is True
    assert database_url_is_azure(url) is True
    assert engine_connect_args(url) == {"connect_timeout": 10}
    pool = engine_pool_kwargs(url)
    assert pool["pool_timeout"] == 30
    assert pool["pool_recycle"] == 300
    assert live_write_timeouts_ms(url) == (2000, 8000)
