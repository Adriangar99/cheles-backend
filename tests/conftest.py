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

os.environ["DATABASE_URL"] = _postgres.get_connection_url()

# Tests must not read a developer's local .env, so every other setting keeps the defaults defined in the code
from app.config import Settings  # noqa: E402

Settings.model_config["env_file"] = None

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.bootstrap import Container, wire  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
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
def container() -> Container:
    """A fresh composition root per test (e.g. no login failures recorded); tests may rewire with their own."""
    fresh = Container.from_environment()
    wire(app, fresh)
    return fresh


@pytest.fixture(autouse=True)
def clean_database(container: Container) -> None:
    """Every test starts from an empty database with the default categories."""
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))
    container.categorization().seed_default_catalog()


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def fake_bank(container: Container) -> FakeEnableBanking:
    """Replaces Enable Banking as the container's banking provider."""
    fake = FakeEnableBanking()
    container.banking_provider = fake
    return fake


@pytest.fixture
def client(fake_bank: FakeEnableBanking) -> Iterator[TestClient]:
    """HTTP client running the app's lifespan; send `X-Test-Client-IP` to choose the client address."""
    with TestClient(ClientIpFromHeader(app), follow_redirects=False) as test_client:
        yield test_client
