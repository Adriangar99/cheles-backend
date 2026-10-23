"""Characterization of `banking/bank-sync`."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main
from app.categorization.infrastructure.orm import CategoryRow
from app.enablebanking import EnableBankingClient
from app.models import Account, BankConnection
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import balance, connect_bank, login, raw_tx

TODAY = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen_today() -> Any:
    with time_machine.travel(TODAY, tick=False) as traveller:
        yield traveller


@pytest.fixture
def user(client: TestClient, db: Session) -> None:
    login(client, db)


def connection_state(client: TestClient, connection_id: int) -> dict[str, Any]:
    connections = client.get("/api/banks").json()["connections"]
    state: dict[str, Any] = next(c for c in connections if c["id"] == connection_id)
    return state


def sync(client: TestClient, connection_id: int) -> dict[str, Any]:
    response = client.post(f"/api/banks/{connection_id}/sync")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# ---------- Scheduled sync ----------


def test_scheduled_run(
    monkeypatch: pytest.MonkeyPatch,
    fake_bank: FakeEnableBanking,
    db: Session,
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scenario: Scheduled run"""
    caplog.set_level(logging.INFO, logger="cheles")
    jobs: list[tuple[Any, ...]] = []

    class SpyScheduler:
        def add_job(self, *args: Any, **kwargs: Any) -> None:
            jobs.append((*args, kwargs))

        def start(self) -> None: ...

        def shutdown(self) -> None: ...

    monkeypatch.setattr(app.main, "BackgroundScheduler", SpyScheduler)
    with TestClient(app.main.app):
        pass
    assert jobs == [(app.main.scheduled_sync, "cron", {"hour": "7,19"})]

    login(client, db)
    connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("5.00", reference="new-1"), raw_tx("6.00", reference="new-2")]

    app.main.scheduled_sync()

    assert "Sincronización programada: 2 movimientos nuevos" in caplog.text


def test_scheduled_sync_failures_are_logged(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """A failure in the scheduled sync is logged and does not propagate (part of «Scheduled sync»)."""

    def broken(db: Session, transactions: object) -> int:
        raise RuntimeError("database down")

    monkeypatch.setattr(app.main, "sync_all", broken)

    app.main.scheduled_sync()

    assert "Falló la sincronización programada" in caplog.text


@pytest.mark.usefixtures("user")
@pytest.mark.parametrize("status", ["expired", "revoked"])
def test_inactive_connections(client: TestClient, db: Session, fake_bank: FakeEnableBanking, status: str) -> None:
    """Scenario: Inactive connections"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    db.get(BankConnection, connection_id).status = status  # type: ignore[union-attr]
    db.commit()
    fake_bank.calls.clear()

    app.main.scheduled_sync()

    assert fake_bank.calls_to("get_transactions") == []


# ---------- Manual sync ----------


@pytest.mark.usefixtures("user")
def test_sync_one_connection(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Sync one connection"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("5.00", reference="a"), raw_tx("6.00", reference="b")]

    assert sync(client, connection_id) == {"new": 2, "status": "active", "error": None}


@pytest.mark.usefixtures("user")
def test_unknown_connection(client: TestClient) -> None:
    """Scenario: Unknown connection"""
    assert client.post("/api/banks/999/sync").status_code == 404


@pytest.mark.usefixtures("user")
def test_sync_everything(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Sync everything"""
    connect_bank(client, fake_bank, [FakeAccount(uid="a")], code="c1")
    connect_bank(client, fake_bank, [FakeAccount(uid="b")], code="c2")
    expired = connect_bank(client, fake_bank, [FakeAccount(uid="c")], code="c3")
    db.get(BankConnection, expired).status = "expired"  # type: ignore[union-attr]
    db.commit()
    fake_bank.transactions.update(
        {
            "a": [raw_tx("1.00", reference="a1")],
            "b": [raw_tx("2.00", reference="b1"), raw_tx("3.00", reference="b2")],
            "c": [raw_tx("4.00", reference="c1")],
        }
    )

    response = client.post("/api/sync")

    assert response.json() == {"new": 3}


# ---------- Expired consent ----------


@pytest.mark.usefixtures("user")
def test_consent_past_its_expiry(
    client: TestClient, fake_bank: FakeEnableBanking, frozen_today: time_machine.Traveller
) -> None:
    """Scenario: Consent past its expiry"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")], valid_until="2026-11-01T00:00:00+00:00")
    last_synced_at = connection_state(client, connection_id)["last_synced_at"]
    fake_bank.calls.clear()
    frozen_today.move_to(datetime(2026, 11, 2, tzinfo=UTC))

    result = sync(client, connection_id)

    assert result == {"new": 0, "status": "expired", "error": None}
    assert fake_bank.calls == []
    assert connection_state(client, connection_id)["last_synced_at"] == last_synced_at


# ---------- Incremental read window ----------


@pytest.mark.usefixtures("user")
def test_account_with_history(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Account with history"""
    fake_bank.transactions["u1"] = [
        raw_tx("1.00", reference="booked", booking_date="2026-10-20"),
        raw_tx("2.00", reference="pending", booking_date="2026-10-22", status="PDNG"),
    ]
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.calls.clear()

    sync(client, connection_id)

    assert fake_bank.calls_to("get_transactions") == [("u1", date(2026, 10, 10))]


@pytest.mark.usefixtures("user")
def test_first_read(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: First read"""
    connect_bank(client, fake_bank, [FakeAccount(uid="u1")])

    assert fake_bank.calls_to("get_transactions") == [("u1", date(2026, 10, 23) - timedelta(days=730))]


@pytest.mark.usefixtures("user")
def test_accounts_without_uid_are_skipped(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Accounts without an Enable Banking uid are skipped (part of «Incremental read window»)."""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    db.add(Account(name="Manual", currency="EUR", role="main", connection_id=connection_id, eb_uid=None))
    db.commit()
    fake_bank.calls.clear()

    sync(client, connection_id)

    assert [args[0] for args in fake_bank.calls_to("get_transactions")] == ["u1"]


def test_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: Pagination"""
    pages = {
        None: {"transactions": [{"n": 1}], "continuation_key": "k2"},
        "k2": {"transactions": [{"n": 2}], "continuation_key": "k3"},
        "k3": {"transactions": [{"n": 3}]},
    }
    requests: list[dict[str, str]] = []

    def fake_request(self: EnableBankingClient, method: str, path: str, **kwargs: Any) -> Any:
        params = dict(kwargs["params"])
        requests.append(params)
        return pages[params.get("continuation_key")]

    monkeypatch.setattr(EnableBankingClient, "_request", fake_request)

    transactions = EnableBankingClient().get_transactions("u1", date(2026, 10, 1))

    assert transactions == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert requests == [
        {"date_from": "2026-10-01"},
        {"date_from": "2026-10-01", "continuation_key": "k2"},
        {"date_from": "2026-10-01", "continuation_key": "k3"},
    ]


# ---------- Storing transactions without duplicates ----------


@pytest.mark.usefixtures("user")
def test_repeated_transaction_in_the_overlap_window(
    client: TestClient, db: Session, fake_bank: FakeEnableBanking
) -> None:
    """Scenario: Repeated transaction in the overlap window"""
    fake_bank.transactions["u1"] = [raw_tx("9.99", reference="r1", remittance=["NETFLIX"])]
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("9.99", reference="r1", remittance=["NETFLIX.COM"])]

    result = sync(client, connection_id)

    assert result["new"] == 0
    [transaction] = db.scalars(select(Transaction)).all()
    assert transaction.description == "NETFLIX.COM"


@pytest.mark.usefixtures("user")
def test_new_transaction(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: New transaction"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("30.00", reference="r1", creditor="MERCADONA")]

    result = sync(client, connection_id)

    assert result["new"] == 1
    transaction = db.scalars(select(Transaction)).one()
    assert transaction.kind == "normal"
    category = db.get(CategoryRow, transaction.category_id) if transaction.category_id else None
    assert category is not None
    assert category.name == "Supermercado"


# ---------- Replacing pending transactions ----------


@pytest.mark.usefixtures("user")
def test_pending_transaction_gets_booked(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Pending transaction gets booked"""
    fake_bank.transactions["u1"] = [raw_tx("20.00", transaction_id="pending-1", status="PDNG")]
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("20.00", reference="booked-1", status="BOOK")]

    sync(client, connection_id)

    assert [(t.external_id, t.status) for t in db.scalars(select(Transaction))] == [("ref:booked-1", "BOOK")]


@pytest.mark.usefixtures("user")
def test_pending_transaction_is_still_pending(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Pending transaction is still pending"""
    fake_bank.transactions["u1"] = [raw_tx("20.00", transaction_id="pending-1", status="PDNG")]
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    pending_id = db.scalars(select(Transaction.id)).one()
    client.patch(f"/api/transactions/{pending_id}", json={"note": "cena"})

    sync(client, connection_id)

    db.expire_all()
    [again] = db.scalars(select(Transaction)).all()
    assert again.id != pending_id
    assert (again.external_id, again.status, again.note) == ("id:pending-1", "PDNG", None)


# ---------- Account balance ----------


@pytest.mark.usefixtures("user")
@pytest.mark.parametrize(
    ("balances", "expected"),
    [
        ([balance("900.00", "CLBD"), balance("1000.00", "ITAV")], 1000.0),
        ([balance("42.00", "OTHR")], 42.0),
        ([], None),
    ],
    ids=["Preferred balance", "Unrecognized type", "No balances"],
)
def test_account_balance(
    client: TestClient, fake_bank: FakeEnableBanking, balances: list[dict[str, Any]], expected: float | None
) -> None:
    """Scenarios: Preferred balance, Unrecognized type, No balances"""
    fake_bank.balances["u1"] = balances

    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])

    account = connection_state(client, connection_id)["accounts"][0]
    assert account["balance"] == expected
    assert account["balance_at"] == "2026-10-23T12:00:00+00:00"


# ---------- Enable Banking errors during sync ----------


@pytest.mark.usefixtures("user")
def test_transient_error(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Transient error"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.transactions["u1"] = [raw_tx("5.00", reference="r1")]
    fake_bank.fail("get_balances", 500, "boom")
    frozen_later = datetime(2026, 10, 23, 13, 0, tzinfo=UTC)

    with time_machine.travel(frozen_later, tick=False):
        result = sync(client, connection_id)

    assert result == {"new": 0, "status": "active", "error": "Enable Banking 500: boom"}
    assert connection_state(client, connection_id)["last_synced_at"] == "2026-10-23T13:00:00+00:00"
    assert db.scalars(select(Transaction)).all() == []


@pytest.mark.usefixtures("user")
@pytest.mark.parametrize("status_code", [401, 403])
def test_access_revoked(client: TestClient, fake_bank: FakeEnableBanking, status_code: int) -> None:
    """Scenario: Access revoked"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.fail("get_transactions", status_code, "consent revoked")

    result = sync(client, connection_id)

    assert result["status"] == "expired"
    assert result["error"] == f"Enable Banking {status_code}: consent revoked"


@pytest.mark.usefixtures("user")
def test_error_on_the_second_account(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Error on the second account"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="a"), FakeAccount(uid="b"), FakeAccount(uid="c")])
    fake_bank.transactions.update({"a": [raw_tx("1.00", reference="a1")], "c": [raw_tx("3.00", reference="c1")]})
    fake_bank.balances["a"] = [balance("100.00", "ITAV")]
    fake_bank.fail("get_transactions", 500, uid="b")
    fake_bank.calls.clear()

    sync(client, connection_id)

    assert [t.external_id for t in db.scalars(select(Transaction))] == ["ref:a1"]
    first = db.scalars(select(Account).where(Account.eb_uid == "a")).one()
    assert first.balance == 100
    assert [args[0] for args in fake_bank.calls_to("get_transactions")] == ["a", "b"]


@pytest.mark.usefixtures("user")
def test_successful_sync_after_an_error(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Successful sync after an error"""
    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    fake_bank.fail("get_transactions", 500)
    assert sync(client, connection_id)["error"] is not None
    fake_bank.recover()

    assert sync(client, connection_id)["error"] is None
    assert connection_state(client, connection_id)["last_error"] is None
