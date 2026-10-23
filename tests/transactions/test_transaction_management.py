"""Characterization of `transactions/transaction-management`."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx


@pytest.fixture
def connection_id(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> int:
    login(client, db)
    fake_bank.transactions["u1"] = [
        raw_tx("12.50", reference="sep-1", booking_date="2026-09-30", creditor="MERCADONA"),
        raw_tx("40.00", reference="oct-1", booking_date="2026-10-01", creditor="Mercadona Valencia"),
        raw_tx("9.99", reference="oct-2", booking_date="2026-10-01", creditor="NETFLIX", status="PDNG"),
        raw_tx("2000.00", debit=False, reference="oct-3", booking_date="2026-10-15", remittance=["NOMINA EMPRESA"]),
    ]
    return connect_bank(client, fake_bank, [FakeAccount(uid="u1", name="Cuenta Online")])


def listed(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/api/transactions", params=params)
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


def transaction_id(db: Session, external_id: str) -> int:
    found: int = db.scalars(select(Transaction.id).where(Transaction.external_id == external_id)).one()
    return found


def category_id(db: Session, name: str) -> int:
    found: int = db.scalars(select(Category.id).where(Category.name == name)).one()
    return found


# ---------- Filtered transaction listing ----------


@pytest.mark.usefixtures("connection_id")
def test_filter_by_month(client: TestClient) -> None:
    """Scenario: Filter by month"""
    october = listed(client, month="2026-10")

    # Newest first; same date ordered by id descending; pending included
    assert [t["date"] for t in october] == ["2026-10-15", "2026-10-01", "2026-10-01"]
    assert [t["counterparty"] for t in october[1:]] == ["NETFLIX", "Mercadona Valencia"]
    assert [t["status"] for t in october].count("PDNG") == 1


@pytest.mark.usefixtures("connection_id")
def test_text_search(client: TestClient) -> None:
    """Scenario: Text search"""
    by_counterparty = listed(client, q="merca")
    by_description = listed(client, q="nomina")

    assert sorted(t["counterparty"] for t in by_counterparty) == ["MERCADONA", "Mercadona Valencia"]
    assert [t["description"] for t in by_description] == ["NOMINA EMPRESA"]


@pytest.mark.usefixtures("connection_id")
def test_other_filters_and_pagination(client: TestClient, db: Session) -> None:
    """`category_id`, `account_id`, `kind`, `limit` and `offset` combine (part of «Filtered transaction listing»)."""
    groceries = category_id(db, "Supermercado")
    account = db.scalars(select(Account.id)).one()

    assert len(listed(client, category_id=groceries, account_id=account, kind="normal")) == 2
    assert listed(client, kind="transfer") == []
    assert [t["date"] for t in listed(client, limit=2, offset=1)] == ["2026-10-01", "2026-10-01"]


@pytest.mark.usefixtures("connection_id")
def test_malformed_month(client: TestClient) -> None:
    """Scenario: Malformed month"""
    assert client.get("/api/transactions", params={"month": "2026-9"}).status_code == 422


@pytest.mark.usefixtures("connection_id")
def test_limit_exceeded(client: TestClient) -> None:
    """Scenario: Limit exceeded"""
    assert client.get("/api/transactions", params={"limit": 1000}).status_code == 422


# ---------- Transaction representation ----------


@pytest.mark.usefixtures("connection_id")
def test_listed_transaction(client: TestClient, db: Session) -> None:
    """Scenario: Listed transaction"""
    account = db.scalars(select(Account)).one()
    client.patch(f"/api/accounts/{account.id}", json={"alias": "Nómina"})

    [transaction] = listed(client, q="MERCADONA", month="2026-09")

    assert transaction == {
        "id": transaction_id(db, "ref:sep-1"),
        "date": "2026-09-30",
        "amount": -12.5,
        "currency": "EUR",
        "status": "BOOK",
        "counterparty": "MERCADONA",
        "description": "",
        "kind": "normal",
        "category_id": category_id(db, "Supermercado"),
        "category_manual": False,
        "account_id": account.id,
        "account": "Nómina",
        "note": None,
    }


# ---------- Manual category ----------


@pytest.mark.usefixtures("connection_id")
def test_assign_a_category(client: TestClient, db: Session) -> None:
    """Scenario: Assign a category"""
    restaurants = category_id(db, "Restaurantes")

    response = client.patch(f"/api/transactions/{transaction_id(db, 'ref:sep-1')}", json={"category_id": restaurants})

    assert response.status_code == 200
    assert (response.json()["category_id"], response.json()["category_manual"]) == (restaurants, True)


@pytest.mark.usefixtures("connection_id")
def test_unknown_category(client: TestClient, db: Session) -> None:
    """Scenario: Unknown category"""
    tx_id = transaction_id(db, "ref:sep-1")

    response = client.patch(f"/api/transactions/{tx_id}", json={"category_id": 999})

    assert response.status_code == 400
    assert response.json() == {"detail": "Categoría inexistente"}
    assert db.get(Transaction, tx_id).category_manual is False  # type: ignore[union-attr]


def test_the_manual_category_is_respected(client: TestClient, db: Session, connection_id: int) -> None:
    """Scenario: The manual category is respected"""
    tx_id = transaction_id(db, "ref:oct-1")
    restaurants = category_id(db, "Restaurantes")
    client.patch(f"/api/transactions/{tx_id}", json={"category_id": restaurants})

    client.post(f"/api/banks/{connection_id}/sync")
    client.post("/api/reprocess")

    db.expire_all()
    assert db.get(Transaction, tx_id).category_id == restaurants  # type: ignore[union-attr]


@pytest.mark.usefixtures("connection_id")
def test_back_to_the_automatic_category(client: TestClient, db: Session) -> None:
    """Scenario: Back to the automatic category"""
    tx_id = transaction_id(db, "ref:oct-1")
    client.patch(f"/api/transactions/{tx_id}", json={"category_id": category_id(db, "Restaurantes")})

    response = client.patch(f"/api/transactions/{tx_id}", json={"clear_category": True})

    assert response.json()["category_manual"] is False
    db.expire_all()
    assert db.get(Transaction, tx_id).category_id == category_id(db, "Supermercado")  # type: ignore[union-attr]


@pytest.mark.usefixtures("connection_id")
def test_unknown_transaction(client: TestClient) -> None:
    """Scenario: Unknown transaction"""
    assert client.patch("/api/transactions/999", json={"note": "x"}).status_code == 404


# ---------- Manual transfer mark (⇄) ----------


@pytest.mark.usefixtures("connection_id")
def test_mark_as_transfer(client: TestClient, db: Session) -> None:
    """Scenario: Mark as transfer"""
    tx_id = transaction_id(db, "ref:oct-1")
    before = client.get("/api/stats/summary", params={"month": "2026-10"}).json()["expenses"]

    response = client.patch(f"/api/transactions/{tx_id}", json={"kind": "transfer"})

    assert response.json()["kind"] == "transfer"
    after = client.get("/api/stats/summary", params={"month": "2026-10"}).json()["expenses"]
    assert before - after == 40.0


@pytest.mark.usefixtures("connection_id")
def test_the_mark_is_lost_on_reprocess_known_defect(client: TestClient, db: Session) -> None:
    """Scenario: The mark is lost on reprocess (known defect)"""
    tx_id = transaction_id(db, "ref:oct-1")
    client.patch(f"/api/transactions/{tx_id}", json={"kind": "transfer"})

    client.post("/api/reprocess")

    db.expire_all()
    transaction = db.get(Transaction, tx_id)
    assert transaction is not None
    assert (transaction.kind, transaction.category_id) == ("normal", category_id(db, "Supermercado"))


def test_the_mark_is_lost_on_sync_known_defect(client: TestClient, db: Session, connection_id: int) -> None:
    """Scenario: The mark is lost on sync (known defect)"""
    # The latest booked transaction, so it falls inside the next sync's 10-day overlap window
    tx_id = transaction_id(db, "ref:oct-3")
    client.patch(f"/api/transactions/{tx_id}", json={"kind": "transfer"})

    client.post(f"/api/banks/{connection_id}/sync")

    db.expire_all()
    assert db.get(Transaction, tx_id).kind == "normal"  # type: ignore[union-attr]


# ---------- Transaction note ----------


@pytest.mark.usefixtures("connection_id")
def test_add_a_note(client: TestClient, db: Session) -> None:
    """Scenario: Add a note"""
    response = client.patch(f"/api/transactions/{transaction_id(db, 'ref:oct-1')}", json={"note": "cena cumple"})

    assert response.json()["note"] == "cena cumple"


@pytest.mark.usefixtures("connection_id")
def test_remove_the_note(client: TestClient, db: Session) -> None:
    """Scenario: Remove the note"""
    tx_id = transaction_id(db, "ref:oct-1")
    client.patch(f"/api/transactions/{tx_id}", json={"note": "cena cumple"})

    response = client.patch(f"/api/transactions/{tx_id}", json={"note": ""})

    assert response.json()["note"] is None
