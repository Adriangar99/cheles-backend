"""Characterization of `platform/service-runtime`."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ROOT


def run_python(code: str, tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Runs Python from an empty directory (so no local .env is read) with only the given environment."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(ROOT), **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "entry_point",
    ["import app.main", "import runpy; runpy.run_module('app.cli', run_name='__main__')"],
    ids=["api", "cli"],
)
def test_missing_database_url(entry_point: str, tmp_path: Path) -> None:
    """Scenario: Missing database URL"""
    result = run_python(entry_point, tmp_path, env={})

    assert result.returncode != 0
    assert "database_url" in result.stderr.lower()


def test_database_url_provided(tmp_path: Path) -> None:
    """Scenario: Database URL provided"""
    url = os.environ["DATABASE_URL"]

    result = run_python(
        "import app.main; from app.db import engine; print(engine.url.render_as_string(hide_password=False))",
        tmp_path,
        env={"DATABASE_URL": url},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == url


def test_health_check(client: TestClient) -> None:
    """Scenario: Health check"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
