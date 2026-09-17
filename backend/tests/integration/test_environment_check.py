from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

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


def test_reports_ready_environment_without_exposing_database_url() -> None:
    started_at = time.perf_counter()
    result = run_check()
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
    assert elapsed_seconds < 30


def test_identifies_missing_database_configuration_without_echoing_other_values(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FLOWSIGHT_ENV=test\n"
        "FLOWSIGHT_API_HOST=127.0.0.1\n"
        "FLOWSIGHT_API_PORT=8000\n"
        "FLOWSIGHT_WORKER_ID=secret-worker-name\n"
        "FLOWSIGHT_PREVIEW_MAX_FPS=5\n",
        encoding="utf-8",
    )

    result = run_check("-EnvFile", str(env_file))

    assert result.returncode != 0
    assert "FLOWSIGHT_DATABASE_URL" in result.stdout
    assert "secret-worker-name" not in result.stdout


def test_identifies_missing_postgresql_tool(tmp_path: Path) -> None:
    missing_bin = tmp_path / "missing-postgres-bin"

    result = run_check("-PostgresBin", str(missing_bin))

    assert result.returncode != 0
    assert "PostgreSQL" in result.stdout
    assert "psql" in result.stdout
