"""Test harness: a throwaway Postgres, a migrated schema and a clean database for every test.

The app builds its SQLAlchemy engine at import time from DATABASE_URL, so the container is started and the
environment is fixed here, before anything imports `app`.
"""

import os
from collections.abc import Iterator

import pytest
from testcontainers.community.postgres import PostgresContainer

_postgres = PostgresContainer("postgres:16-alpine", driver="psycopg")
_postgres.start()

os.environ.update(
    {
        "DATABASE_URL": _postgres.get_connection_url(),
        # Explicit values so a developer's local .env cannot change test results
        "PUBLIC_URL": "http://localhost:3000",
        "COOKIE_SECURE": "false",
        "EB_APPLICATION_ID": "test-application",
        "EB_COUNTRY": "ES",
        "EB_CONSENT_DAYS": "180",
        "SESSION_DAYS": "14",
        "SYNC_HOURS": "7,19",
        "INITIAL_HISTORY_DAYS": "730",
    }
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.categorize import seed_categories  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_throttle  # noqa: E402
from tests.fakes import FakeEnableBanking  # noqa: E402
from tests.helpers import ClientIpFromHeader, migrate_to_head  # noqa: E402

APP_TABLES = (
    "transactions",
    "rules",
    "categories",
    "accounts",
    "bank_connections",
    "pending_auths",
    "login_sessions",
    "users",
)


def pytest_sessionstart(session: pytest.Session) -> None:
    migrate_to_head(os.environ["DATABASE_URL"])


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    engine.dispose()
    _postgres.stop()


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Every test starts from an empty database with the default categories, and no login failures recorded."""
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        seed_categories(db)
    login_throttle._failures.clear()


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def fake_bank(monkeypatch: pytest.MonkeyPatch) -> FakeEnableBanking:
    """Replaces Enable Banking everywhere the app instantiates its client."""
    fake = FakeEnableBanking()
    monkeypatch.setattr("app.main.EnableBankingClient", lambda: fake)
    monkeypatch.setattr("app.sync.EnableBankingClient", lambda: fake)
    return fake


@pytest.fixture
def client(fake_bank: FakeEnableBanking) -> Iterator[TestClient]:
    """HTTP client running the app's lifespan; send `X-Test-Client-IP` to choose the client address."""
    with TestClient(ClientIpFromHeader(app), follow_redirects=False) as test_client:
        yield test_client
