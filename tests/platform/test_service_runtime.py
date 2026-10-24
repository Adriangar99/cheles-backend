"""Characterization of `platform/service-runtime`."""

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from tests.helpers import ROOT

APP_TABLES = {
    "accounts",
    "bank_connections",
    "categories",
    "login_sessions",
    "pending_auths",
    "rules",
    "transactions",
    "users",
}


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


@pytest.fixture
def scratch_database_url() -> Iterator[str]:
    """A brand-new empty database in the test Postgres, dropped afterwards."""
    name = f"scratch_{uuid.uuid4().hex[:12]}"
    admin = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    yield make_url(os.environ["DATABASE_URL"]).set(database=name).render_as_string(hide_password=False)
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


HEAD = ScriptDirectory(str(ROOT / "migrations")).get_current_head()


def create_pre_migration_schema(database_url: str, tmp_path: Path) -> None:
    """The schema the old create_all startup built: exactly the baseline revision, with no version recorded."""
    result = run_python(
        "from alembic import command; from app.migrate import BASELINE, _config; command.upgrade(_config(), BASELINE)",
        tmp_path,
        env={"DATABASE_URL": database_url},
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
    engine.dispose()


def run_migrate(database_url: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    result = run_python(
        "import runpy, sys; sys.argv = ['app.cli', 'migrate']; runpy.run_module('app.cli', run_name='__main__')",
        tmp_path,
        env={"DATABASE_URL": database_url},
    )
    assert result.returncode == 0, result.stderr
    return result


def schema_version(database_url: str) -> str | None:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    return version


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    return names


def test_empty_database(scratch_database_url: str, tmp_path: Path) -> None:
    """Scenario: Empty database"""
    run_migrate(scratch_database_url, tmp_path)

    assert table_names(scratch_database_url) == APP_TABLES | {"alembic_version"}
    assert schema_version(scratch_database_url) == HEAD


def test_database_already_up_to_date(scratch_database_url: str, tmp_path: Path) -> None:
    """Scenario: Database already up to date"""
    run_migrate(scratch_database_url, tmp_path)
    engine = create_engine(scratch_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO categories (name, kind, icon, color) VALUES ('Mascotas', 'expense', '🐾', '#000')")
        )

    run_migrate(scratch_database_url, tmp_path)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM categories")).scalars().all() == ["Mascotas"]
    engine.dispose()
    assert schema_version(scratch_database_url) == HEAD


def test_existing_database_created_before_migrations(scratch_database_url: str, tmp_path: Path) -> None:
    """Scenario: Existing database created before migrations"""
    create_pre_migration_schema(scratch_database_url, tmp_path)
    engine = create_engine(scratch_database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (username, password_hash, totp_secret) VALUES ('ana', 'h', 's')"))
        connection.execute(
            text("INSERT INTO categories (name, kind, icon, color) VALUES ('Mascotas', 'expense', '🐾', '#000')")
        )

    result = run_migrate(scratch_database_url, tmp_path)

    assert "baseline" in (result.stdout + result.stderr).lower()
    assert schema_version(scratch_database_url) == HEAD
    with engine.connect() as connection:
        assert connection.execute(text("SELECT username FROM users")).scalars().all() == ["ana"]
        assert connection.execute(text("SELECT name FROM categories")).scalars().all() == ["Mascotas"]
    engine.dispose()


def test_create_user_migrates_an_empty_database(scratch_database_url: str, tmp_path: Path) -> None:
    """`create-user` works on a database without schema, creating it through the migrations."""
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "create-user", "ana"],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(ROOT), "DATABASE_URL": scratch_database_url},
        input="correct horse battery\ncorrect horse battery\n",
        capture_output=True,
        text=True,
        timeout=60,
        start_new_session=True,  # no controlling terminal, so getpass reads the password from stdin
    )

    assert result.returncode == 0, result.stderr
    assert schema_version(scratch_database_url) == HEAD
    engine = create_engine(scratch_database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT username FROM users")).scalars().all() == ["ana"]
    engine.dispose()


def test_health_check(client: TestClient) -> None:
    """Scenario: Health check"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
