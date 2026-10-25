"""Shared helpers for characterization tests: migrations, client IP, login, bank connection and raw payloads."""

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pyotp
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from app.bootstrap import Container
from tests.fakes import FakeAccount, FakeEnableBanking

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "correct horse battery"


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["configure_logger"] = False
    return config


def migrate_to_head(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        config = alembic_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    engine.dispose()


class ClientIpFromHeader:
    """Test-only ASGI wrapper: Starlette's TestClient cannot choose the client address, this header can."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == b"x-test-client-ip":
                    scope = {**scope, "client": (value.decode(), 50000)}
        await self.app(scope, receive, send)


def create_user(db: Session, username: str = "ana", password: str = PASSWORD) -> str:
    """Creates the single user through the identity use case and returns its TOTP secret."""
    return Container.from_environment().identity().create_user(username, password).secret


def login(client: TestClient, db: Session, username: str = "ana") -> str:
    """Creates the user, logs in and returns the TOTP secret; the client keeps the session cookie."""
    secret = create_user(db, username)
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD, "code": pyotp.TOTP(secret).now()}
    )
    assert response.status_code == 200, response.text
    return secret


def connect_bank(
    client: TestClient,
    fake: FakeEnableBanking,
    accounts: list[FakeAccount],
    bank: str = "BBVA",
    code: str = "auth-code",
    valid_until: str = "2027-04-01T00:00:00+00:00",
) -> int:
    """Runs the whole authorization flow against the fake bank and returns the new connection id."""
    response = client.post("/api/banks/connect", json={"name": bank})
    assert response.status_code == 200, response.text
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    fake.add_session(code, accounts, valid_until)
    callback = client.get("/api/banks/callback", params={"code": code, "state": state})
    assert callback.headers["location"] == "/bancos?connected=1", callback.headers
    connections = client.get("/api/banks").json()["connections"]
    connection_id: int = connections[-1]["id"]
    return connection_id


def raw_tx(
    amount: str,
    *,
    debit: bool = True,
    booking_date: str | None = "2026-10-03",
    reference: str | None = None,
    transaction_id: str | None = None,
    status: str | None = "BOOK",
    creditor: str | None = None,
    creditor_iban: str | None = None,
    debtor: str | None = None,
    debtor_iban: str | None = None,
    remittance: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """A transaction as Enable Banking returns it (only the fields the app reads)."""
    raw: dict[str, Any] = {
        "transaction_amount": {"amount": amount, "currency": "EUR"},
        "credit_debit_indicator": "DBIT" if debit else "CRDT",
        "remittance_information": remittance if remittance is not None else [],
        **extra,
    }
    optional = {
        "booking_date": booking_date,
        "entry_reference": reference,
        "transaction_id": transaction_id,
        "status": status,
        "creditor": {"name": creditor} if creditor else None,
        "creditor_account": {"iban": creditor_iban} if creditor_iban else None,
        "debtor": {"name": debtor} if debtor else None,
        "debtor_account": {"iban": debtor_iban} if debtor_iban else None,
    }
    raw.update({key: value for key, value in optional.items() if value is not None})
    return raw


def balance(amount: str, balance_type: str) -> dict[str, Any]:
    return {"balance_type": balance_type, "balance_amount": {"amount": amount, "currency": "EUR"}}


def stored_row[M](db: Session, model: type[M], row_id: int | None) -> M:
    """The row as currently stored: the session is expired first, so changes made through the API are seen."""
    db.expire_all()
    row = db.get(model, row_id) if row_id is not None else None
    if row is None:
        raise AssertionError(f"No {model.__name__} stored with id {row_id}")
    return row
