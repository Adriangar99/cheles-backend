"""Characterization of `banking/bank-connection`."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.infrastructure.enable_banking import EnableBankingClient
from app.banking.infrastructure.orm import AccountRow as Account
from app.banking.infrastructure.orm import BankConnectionRow as BankConnection
from app.banking.infrastructure.orm import PendingAuthRow as PendingAuth
from app.bootstrap import Container
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx


@pytest.fixture
def user(client: TestClient, db: Session) -> None:
    login(client, db)


def start_authorization(client: TestClient, bank: str = "BBVA") -> str:
    response = client.post("/api/banks/connect", json={"name": bank})
    assert response.status_code == 200, response.text
    state: str = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    return state


# ---------- List of available banks ----------


@pytest.mark.usefixtures("user")
def test_available_banks(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Available banks"""
    response = client.get("/api/banks/available")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "BBVA", "country": "ES", "logo": "https://logos.example/bbva.png"},
        {"name": "Revolut", "country": "ES", "logo": "https://logos.example/revolut.png"},
    ]
    assert fake_bank.calls_to("list_aspsps") == [("ES",)]


@pytest.mark.usefixtures("user")
def test_enable_banking_error(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Enable Banking error"""
    fake_bank.fail("list_aspsps", 503, {"error": "down"})

    response = client.get("/api/banks/available")

    assert response.status_code == 502
    assert response.json() == {"detail": "Enable Banking: {'error': 'down'}"}


# ---------- Starting authorization with a bank ----------


@pytest.mark.usefixtures("user")
def test_authorization_started(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Authorization started"""
    before = datetime.now(UTC)

    response = client.post("/api/banks/connect", json={"name": "BBVA"})

    pending = db.scalars(select(PendingAuth)).one()
    assert (pending.aspsp_name, pending.aspsp_country) == ("BBVA", "ES")
    assert len(pending.state) >= 32
    assert response.json() == {"url": f"https://bank.example/BBVA/authorize?state={pending.state}"}
    [(bank, country, state, redirect_url, valid_until)] = fake_bank.calls_to("start_auth")
    assert (bank, country, state) == ("BBVA", "ES", pending.state)
    assert redirect_url == "http://localhost:3000/api/banks/callback"
    assert before + timedelta(days=180) <= valid_until <= datetime.now(UTC) + timedelta(days=180)


@pytest.mark.usefixtures("user")
def test_error_while_starting(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Error while starting"""
    fake_bank.fail("start_auth", 400, "invalid aspsp")

    response = client.post("/api/banks/connect", json={"name": "BBVA"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Enable Banking: invalid aspsp"}


# ---------- Authorization callback ----------


@pytest.mark.usefixtures("user")
def test_authorization_completed(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Authorization completed"""
    state = start_authorization(client)
    fake_bank.add_session(
        "code-1", [FakeAccount(uid="uid-1"), FakeAccount(uid="uid-2")], valid_until="2027-04-01T00:00:00+00:00"
    )

    response = client.get("/api/banks/callback", params={"code": "code-1", "state": state})

    assert response.status_code == 303
    assert response.headers["location"] == "/bancos?connected=1"
    connection = db.scalars(select(BankConnection)).one()
    assert (connection.status, connection.session_id) == ("active", "session-code-1")
    assert connection.valid_until == datetime(2027, 4, 1, tzinfo=UTC)
    accounts = db.scalars(select(Account).order_by(Account.id)).all()
    assert [(a.eb_uid, a.connection_id) for a in accounts] == [("uid-1", connection.id), ("uid-2", connection.id)]
    assert db.scalars(select(PendingAuth)).all() == []


@pytest.mark.usefixtures("user")
@pytest.mark.parametrize("problem", ["bank error", "no code", "unknown state"])
def test_the_bank_returns_an_error_or_data_is_missing(
    client: TestClient, db: Session, fake_bank: FakeEnableBanking, problem: str
) -> None:
    """Scenario: The bank returns an error or data is missing"""
    state = start_authorization(client)
    fake_bank.add_session("code-1", [FakeAccount(uid="uid-1")])
    params = {
        "bank error": {"code": "code-1", "state": state, "error": "access_denied"},
        "no code": {"state": state},
        "unknown state": {"code": "code-1", "state": "not-a-pending-state"},
    }[problem]

    response = client.get("/api/banks/callback", params=params)

    assert response.status_code == 303
    assert response.headers["location"] == "/bancos?error=1"
    assert db.scalars(select(BankConnection)).all() == []


@pytest.mark.usefixtures("user")
def test_session_creation_fails(client: TestClient, db: Session) -> None:
    """Scenario: Session creation fails"""
    state = start_authorization(client)

    response = client.get("/api/banks/callback", params={"code": "unknown-code", "state": state})

    assert response.headers["location"] == "/bancos?error=1"
    assert db.scalars(select(BankConnection)).all() == []


@pytest.mark.usefixtures("user")
def test_the_first_sync_fails(
    client: TestClient, db: Session, fake_bank: FakeEnableBanking, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: The first sync fails"""
    fake_bank.fail("get_transactions", error=RuntimeError("unexpected"))

    connect_bank(client, fake_bank, [FakeAccount(uid="uid-1")])

    assert "Falló la primera sincronización" in caplog.text
    assert db.scalars(select(BankConnection)).one().status == "active"


# ---------- Re-linking known accounts on reconnection ----------


@pytest.mark.usefixtures("user")
def test_reconnected_account_matched_by_hash(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Reconnected account matched by hash"""
    fake_bank.transactions["uid-old"] = [raw_tx("10.00", reference="r1")]
    connect_bank(client, fake_bank, [FakeAccount(uid="uid-old", identification_hash="hash-1")], code="first")
    account = db.scalars(select(Account)).one()
    client.patch(f"/api/accounts/{account.id}", json={"role": "savings", "alias": "Hucha"})

    second = connect_bank(client, fake_bank, [FakeAccount(uid="uid-new", identification_hash="hash-1")], code="second")

    db.expire_all()
    [reused] = db.scalars(select(Account)).all()
    assert reused.id == account.id
    assert (reused.connection_id, reused.eb_uid) == (second, "uid-new")
    assert (reused.role, reused.alias) == ("savings", "Hucha")
    assert len(db.scalars(select(Transaction).where(Transaction.account_id == account.id)).all()) == 1


@pytest.mark.usefixtures("user")
def test_reconnected_account_matched_by_iban(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Reconnected account matched by IBAN"""
    connect_bank(
        client, fake_bank, [FakeAccount(uid="u1", identification_hash="hash-1", iban="ES12 3456")], code="first"
    )

    connect_bank(
        client, fake_bank, [FakeAccount(uid="u2", identification_hash="hash-2", iban="es123456")], code="second"
    )

    db.expire_all()
    [account] = db.scalars(select(Account)).all()
    assert (account.eb_uid, account.identification_hash, account.iban) == ("u2", "hash-2", "ES123456")


@pytest.mark.usefixtures("user")
def test_new_account(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: New account"""
    connect_bank(
        client,
        fake_bank,
        [
            FakeAccount(uid="u1", name="Cuenta Online", currency="USD"),
            FakeAccount(uid="u2", name=None, currency=None),
        ],
        bank="BBVA",
    )

    accounts = db.scalars(select(Account).order_by(Account.id)).all()
    assert [(a.name, a.role, a.currency) for a in accounts] == [
        ("Cuenta Online", "main", "USD"),
        ("BBVA", "main", "EUR"),
    ]


@pytest.mark.usefixtures("user")
def test_the_bank_sends_no_iban(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: The bank sends no IBAN"""
    connect_bank(client, fake_bank, [FakeAccount(uid="u1", identification_hash="hash-1", iban="ES123456")], code="a")

    connect_bank(client, fake_bank, [FakeAccount(uid="u2", identification_hash="hash-1", iban=None)], code="b")

    db.expire_all()
    assert db.scalars(select(Account)).one().iban == "ES123456"


# ---------- Removing a connection ----------


def banks(client: TestClient) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/banks").json()
    return body


@pytest.mark.usefixtures("user")
def test_remove_a_connection(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Remove a connection"""
    fake_bank.transactions["a1"] = [raw_tx("10.00", reference="t1")]
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="a1"), FakeAccount(uid="a2")], code="c1")
    savings = banks(client)["connections"][0]["accounts"][1]["id"]
    client.patch(f"/api/accounts/{savings}", json={"role": "savings"})

    response = client.delete(f"/api/banks/{connection_id}")

    assert response.status_code == 204
    assert fake_bank.calls_to("delete_session") == [("session-c1",)]
    after = banks(client)
    assert after["connections"] == []
    assert sorted(a["role"] for a in after["detached_accounts"]) == ["main", "savings"]
    assert len(client.get("/api/transactions").json()) == 1


@pytest.mark.usefixtures("user")
def test_enable_banking_fails_to_close_the_session(
    client: TestClient, fake_bank: FakeEnableBanking, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: Enable Banking fails to close the session"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="a1")])
    fake_bank.fail("delete_session", 500, "session lost")

    response = client.delete(f"/api/banks/{connection_id}")

    assert response.status_code == 204
    assert "session lost" in caplog.text
    assert banks(client)["connections"] == []


@pytest.mark.usefixtures("user")
def test_unknown_connection(client: TestClient) -> None:
    """Scenario: Unknown connection"""
    assert client.delete("/api/banks/999").status_code == 404


@pytest.mark.usefixtures("user")
def test_reconnecting_after_removing(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Reconnecting after removing"""
    first = connect_bank(client, fake_bank, [FakeAccount(uid="old", identification_hash="h1")], code="c1")
    account = banks(client)["connections"][0]["accounts"][0]["id"]
    client.patch(f"/api/accounts/{account}", json={"role": "savings", "alias": "Colchón"})
    client.delete(f"/api/banks/{first}")

    second = connect_bank(client, fake_bank, [FakeAccount(uid="new", identification_hash="h1")], code="c2")

    after = banks(client)
    [connection] = after["connections"]
    assert connection["id"] == second
    assert [(a["id"], a["role"], a["name"]) for a in connection["accounts"]] == [(account, "savings", "Colchón")]
    assert after["detached_accounts"] == []


# ---------- Abandoned authorizations are cleaned up ----------


def pending_states(db: Session) -> set[str]:
    db.expire_all()
    return set(db.scalars(select(PendingAuth.state)))


@pytest.mark.usefixtures("user")
@pytest.mark.parametrize(
    ("minutes_later", "kept"),
    [pytest.param(120, False, id="old"), pytest.param(10, True, id="recent")],
)
def test_pending_authorizations_by_age(client: TestClient, db: Session, minutes_later: int, kept: bool) -> None:
    """Scenarios: Old pending authorization, Recent pending authorization"""
    start = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
    with time_machine.travel(start, tick=False):
        first = start_authorization(client)
    with time_machine.travel(start + timedelta(minutes=minutes_later), tick=False):
        second = start_authorization(client)

    assert pending_states(db) == ({first, second} if kept else {second})


# ---------- Missing Enable Banking configuration ----------

NOT_CONFIGURED = {"detail": "Enable Banking no está configurado"}


def use_unconfigured_provider(container: Container, *, application_id: str = "", key_path: str | None = None) -> None:
    """The real Enable Banking client, with the configuration the test leaves out."""
    provider = EnableBankingClient()
    provider.application_id = application_id
    if key_path is not None:
        provider.private_key_path = key_path
    container.banking_provider = provider


@pytest.mark.usefixtures("user")
def test_listing_banks_without_configuration(client: TestClient, container: Container) -> None:
    """Scenario: Listing banks without configuration"""
    use_unconfigured_provider(container)

    response = client.get("/api/banks/available")

    assert (response.status_code, response.json()) == (503, NOT_CONFIGURED)


@pytest.mark.usefixtures("user")
def test_connecting_without_a_private_key(client: TestClient, container: Container, tmp_path: Path) -> None:
    """Scenario: Connecting without a private key"""
    use_unconfigured_provider(container, application_id="app-id", key_path=str(tmp_path / "missing.pem"))

    response = client.post("/api/banks/connect", json={"name": "BBVA"})

    assert (response.status_code, response.json()) == (503, NOT_CONFIGURED)


@pytest.mark.usefixtures("user")
def test_syncing_without_configuration(
    client: TestClient, db: Session, fake_bank: FakeEnableBanking, container: Container
) -> None:
    """Scenario: Syncing without configuration"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    before = db.get(BankConnection, connection_id)
    assert before is not None
    stored = (before.last_error, before.status, before.last_synced_at)
    use_unconfigured_provider(container)

    response = client.post(f"/api/banks/{connection_id}/sync")

    assert (response.status_code, response.json()) == (503, NOT_CONFIGURED)
    db.expire_all()
    after = db.get(BankConnection, connection_id)
    assert after is not None
    assert (after.last_error, after.status, after.last_synced_at) == stored


@pytest.mark.usefixtures("user")
def test_syncing_everything_without_configuration(
    client: TestClient, fake_bank: FakeEnableBanking, container: Container
) -> None:
    """Scenario: Syncing everything without configuration"""
    connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    use_unconfigured_provider(container)

    response = client.post("/api/sync")

    assert (response.status_code, response.json()) == (503, NOT_CONFIGURED)


@pytest.mark.usefixtures("user")
def test_callback_without_configuration(client: TestClient, container: Container) -> None:
    """Scenario: Callback without configuration"""
    state = start_authorization(client)
    use_unconfigured_provider(container)

    response = client.get("/api/banks/callback", params={"code": "auth-code", "state": state})

    assert response.headers["location"] == "/bancos?error=1"
