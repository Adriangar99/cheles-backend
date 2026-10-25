"""Characterization of `transactions/reprocessing`."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.banking.infrastructure.orm import AccountRow as Account
from app.categorization.infrastructure.orm import CategoryRow as Category
from app.db import SessionLocal
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx, stored_row

SAVINGS_IBAN = "ES2222222222222222222222"


@pytest.fixture
def stored(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    login(client, db)
    fake_bank.transactions["main"] = [
        raw_tx("40.00", reference="groceries", creditor="MERCADONA"),
        raw_tx("300.00", reference="to-savings", creditor_iban=SAVINGS_IBAN),
        raw_tx("15.00", reference="gas", creditor="GASOLINERA PEPE"),
    ]
    connect_bank(client, fake_bank, [FakeAccount(uid="main"), FakeAccount(uid="savings")])
    fake_bank.calls.clear()


def by_reference(db: Session, reference: str) -> Transaction:
    db.expire_all()
    return db.scalars(select(Transaction).where(Transaction.external_id == f"ref:{reference}")).one()


def category_name(transaction: Transaction) -> str | None:
    if transaction.category_id is None:
        return None
    with SessionLocal() as db:
        category = db.get(Category, transaction.category_id)
        return category.name if category else None


# ---------- Reprocessing from the original payload ----------


@pytest.mark.usefixtures("stored")
def test_full_reprocess(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Full reprocess"""
    response = client.post("/api/reprocess")

    assert response.json() == {"processed": 3}
    assert fake_bank.calls == []


@pytest.mark.usefixtures("stored")
def test_normalized_fields_are_recomputed_from_raw(client: TestClient, db: Session) -> None:
    """Normalized fields come back from `raw` (part of «Reprocessing from the original payload»)."""
    transaction = by_reference(db, "groceries")
    transaction.description = "edited by hand in the database"
    transaction.amount = Decimal("0")
    db.commit()

    client.post("/api/reprocess")

    transaction = by_reference(db, "groceries")
    assert (transaction.description, float(transaction.amount)) == ("", -40.0)


@pytest.mark.usefixtures("stored")
def test_the_external_id_is_kept(client: TestClient, db: Session) -> None:
    """Scenario: The external id is kept"""
    transaction = by_reference(db, "groceries")
    transaction.raw = {**transaction.raw, "entry_reference": "a-different-reference"}
    flag_modified(transaction, "raw")
    db.commit()

    client.post("/api/reprocess")
    assert stored_row(db, Transaction, transaction.id).external_id == "ref:groceries"


@pytest.mark.usefixtures("stored")
def test_new_own_account(client: TestClient, db: Session) -> None:
    """Scenario: New own account"""
    assert by_reference(db, "to-savings").kind == "normal"
    savings = db.scalars(select(Account).where(Account.eb_uid == "savings")).one()
    savings.iban = SAVINGS_IBAN
    db.commit()

    client.post("/api/reprocess")

    assert by_reference(db, "to-savings").kind == "transfer"


@pytest.mark.usefixtures("stored")
def test_imported_transaction(client: TestClient, db: Session) -> None:
    """Scenario: Imported transaction"""
    account = db.scalars(select(Account).where(Account.eb_uid == "main")).one()
    restaurants = db.scalars(select(Category.id).where(Category.name == "Restaurantes")).one()
    row = {"Fecha": "03/05/2025", "Categoria": "Comer en casa o fuera", "Cantidad": "-8.80", "Nota": "Churros"}
    imported = Transaction(
        account_id=account.id,
        external_id="ml:churros",
        booking_date=date(2025, 5, 3),
        amount=Decimal("-8.80"),
        currency="EUR",
        status="BOOK",
        description="Churros",
        raw=row,
        source="import",
        category_id=restaurants,
        category_manual=True,
    )
    db.add(imported)
    db.commit()

    assert client.post("/api/reprocess").json() == {"processed": 4}

    db.expire_all()
    kept = db.scalars(select(Transaction).where(Transaction.external_id == "ml:churros")).one()
    assert (kept.booking_date, kept.amount, kept.description) == (date(2025, 5, 3), Decimal("-8.80"), "Churros")
    assert category_name(kept) == "Restaurantes"


# ---------- Reprocessing respects manual edits ----------


@pytest.mark.usefixtures("stored")
def test_manual_category(client: TestClient, db: Session) -> None:
    """Scenario: Manual category"""
    leisure = db.scalars(select(Category.id).where(Category.name == "Ocio")).one()
    client.patch(f"/api/transactions/{by_reference(db, 'groceries').id}", json={"category_id": leisure})

    client.post("/api/reprocess")

    assert category_name(by_reference(db, "groceries")) == "Ocio"


@pytest.mark.usefixtures("stored")
def test_note(client: TestClient, db: Session) -> None:
    """Scenario: Note"""
    client.patch(f"/api/transactions/{by_reference(db, 'groceries').id}", json={"note": "compra semanal"})

    client.post("/api/reprocess")

    assert by_reference(db, "groceries").note == "compra semanal"


@pytest.mark.usefixtures("stored")
def test_manual_kind(client: TestClient, db: Session) -> None:
    """Scenario: Manual kind"""
    client.patch(f"/api/transactions/{by_reference(db, 'groceries').id}", json={"kind": "transfer"})

    client.post("/api/reprocess")

    groceries = by_reference(db, "groceries")
    assert (groceries.kind, groceries.kind_manual) == ("transfer", True)


# ---------- Actions that trigger a reprocess ----------


@pytest.mark.usefixtures("stored")
def test_creating_a_rule(client: TestClient, db: Session) -> None:
    """Scenario: Creating a rule"""
    assert category_name(by_reference(db, "gas")) == "Otros gastos"
    transport = db.scalars(select(Category.id).where(Category.name == "Transporte")).one()

    response = client.post("/api/rules", json={"pattern": "gasolinera pepe", "category_id": transport})

    assert response.json() == {"processed": 3}
    assert category_name(by_reference(db, "gas")) == "Transporte"
