from concurrent.futures import ThreadPoolExecutor

from flowsight.core.config import Settings
from flowsight.core.local_webcam import configure_local_webcam


def settings(**overrides):
    return Settings(
        _env_file=None,
        FLOWSIGHT_ENV="test",
        FLOWSIGHT_DATABASE_URL="postgresql+psycopg://local/test",
        FLOWSIGHT_WORKER_ID="test-worker",
        **overrides,
    )


def test_api_and_worker_share_generated_credentials_without_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("FLOWSIGHT_MACHINE_ID", raising=False)
    monkeypatch.delenv("FLOWSIGHT_LIVE_CHANNEL_TOKEN", raising=False)
    first = configure_local_webcam(settings(), directory=tmp_path)
    second = configure_local_webcam(settings(), directory=tmp_path)
    assert first.machine_id == second.machine_id
    assert first.machine_id.startswith("local-")
    assert len(first.live_channel_token.get_secret_value()) >= 32
    assert (
        first.live_channel_token.get_secret_value() == second.live_channel_token.get_secret_value()
    )


def test_parallel_startup_uses_one_identity(tmp_path, monkeypatch):
    monkeypatch.delenv("FLOWSIGHT_MACHINE_ID", raising=False)
    monkeypatch.delenv("FLOWSIGHT_LIVE_CHANNEL_TOKEN", raising=False)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: configure_local_webcam(settings(), directory=tmp_path), range(16)
            )
        )
    assert len({item.machine_id for item in results}) == 1
    assert len({item.live_channel_token.get_secret_value() for item in results}) == 1


def test_explicit_existing_settings_are_preserved(tmp_path):
    configured = settings(
        FLOWSIGHT_MACHINE_ID="existing-machine", FLOWSIGHT_LIVE_CHANNEL_TOKEN="existing-token"
    )
    assert configure_local_webcam(configured, directory=tmp_path) is configured
    assert list(tmp_path.iterdir()) == []
