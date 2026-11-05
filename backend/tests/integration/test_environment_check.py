from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from conftest import destructive_database_url, prepare_empty_schema

ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT_DIR / "scripts" / "check-environment.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Diagnóstico del entorno Windows")


def run_check(*arguments: str) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SCRIPT_PATH), "-OutputFormat", "Json", *arguments],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def write_env_file(tmp_path: Path, *, database_url: str | None) -> Path:
    env_file = tmp_path / ".env"
    values = {
        "FLOWSIGHT_ENV": "test",
        "FLOWSIGHT_API_HOST": "127.0.0.1",
        "FLOWSIGHT_API_PORT": "8000",
        "FLOWSIGHT_WORKER_ID": "secret-worker-name",
        "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
        "FLOWSIGHT_DETECTOR": "fake",
        "VITE_API_BASE_URL": "http://127.0.0.1:8000",
        "VITE_WS_BASE_URL": "ws://127.0.0.1:8000",
    }
    if database_url is not None:
        values["FLOWSIGHT_DATABASE_URL"] = database_url
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8"
    )
    return env_file


def test_reports_ready_environment_without_exposing_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    prepare_empty_schema(database_url)
    env_file = write_env_file(tmp_path, database_url=database_url)
    started_at = time.perf_counter()
    result = run_check("-EnvFile", str(env_file))
    elapsed_seconds = time.perf_counter() - started_at

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "ready"
    assert {check["component"] for check in report["checks"]} >= {
        "Python",
        "Dependencias backend",
        "Node.js",
        "npm",
        "Dependencias frontend",
        "PostgreSQL",
        "Configuracion",
        "Base de datos",
    }
    assert "postgresql+psycopg://" not in result.stdout
    assert "FLOWSIGHT_DATABASE_URL=" not in result.stdout
    assert database_url not in result.stdout
    assert elapsed_seconds < 30


def test_identifies_missing_database_configuration_without_echoing_other_values(
    tmp_path: Path,
) -> None:
    env_file = write_env_file(tmp_path, database_url=None)

    result = run_check("-EnvFile", str(env_file))

    assert result.returncode != 0
    assert "FLOWSIGHT_DATABASE_URL" in result.stdout
    assert "secret-worker-name" not in result.stdout


def test_identifies_missing_postgresql_tool(tmp_path: Path) -> None:
    missing_bin = tmp_path / "missing-postgres-bin"
    env_file = write_env_file(
        tmp_path, database_url="postgresql+psycopg://postgres@127.0.0.1:1/unreachable_test"
    )

    result = run_check("-EnvFile", str(env_file), "-PostgresBin", str(missing_bin))

    assert result.returncode != 0
    assert "PostgreSQL" in result.stdout
    assert "psql" in result.stdout
