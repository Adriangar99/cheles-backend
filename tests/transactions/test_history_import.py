"""Characterization of `transactions/history-import`."""

import base64
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.infrastructure.orm import AccountRow as Account
from app.categorization.infrastructure.orm import CategoryRow as Category
from app.shared.money import Money
from app.transactions.domain.moneylover import read_export
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx
from tests.transactions.moneylover_export import HEADER, export, row

Targets = dict[str, int | str | None]


@pytest.fixture
def bank_account(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> int:
    """A logged-in user with a bank account «Nómina» whose bank transactions start on 2026-07-01."""
    login(client, db)
    fake_bank.transactions["main"] = [
        raw_tx("12.00", reference="first", booking_date="2026-07-01"),
        raw_tx("30.00", reference="later", booking_date="2026-08-10"),
    ]
    connect_bank(client, fake_bank, [FakeAccount(uid="main", name="Nómina")])
    account_id: int = db.scalars(select(Account.id).where(Account.eb_uid == "main")).one()
    return account_id


def body(content: bytes, accounts: Targets) -> dict[str, Any]:
    return {"file": base64.b64encode(content).decode(), "accounts": accounts}


def preview(client: TestClient, content: bytes, accounts: Targets) -> Any:
    response = client.post("/api/imports/preview", json=body(content, accounts))
    assert response.status_code == 200, response.text
    return response.json()


def wallet(result: Any, name: str) -> Any:
    return next(w for w in result["wallets"] if w["name"] == name)


def imported(db: Session) -> list[Transaction]:
    db.expire_all()
    return list(db.scalars(select(Transaction).where(Transaction.source == "import")))


def category_of(db: Session, transaction: Transaction) -> str | None:
    if transaction.category_id is None:
        return None
    return db.scalars(select(Category.name).where(Category.id == transaction.category_id)).one()


# ---------- Reading a MoneyLover export ----------


def test_utf16_export() -> None:
    """Scenario: UTF-16 export"""
    [read] = read_export(export(row("25/10/2026", "Gasolina", "-47.80", "", "Cuenta Principal")))

    assert (read.wallet, read.booking_date, read.amount, read.category, read.note) == (
        "Cuenta Principal",
        date(2026, 10, 25),
        Money(Decimal("-47.80"), "EUR"),
        "Gasolina",
        "",
    )


def test_utf8_export_with_reordered_columns_and_quoted_fields() -> None:
    """Requirement detail: UTF-8 is read too, columns may come in any order and fields may be quoted."""
    header = list(reversed(HEADER))
    content = export(list(reversed(row(note="Cena, cine y copas", amount="-60.00"))), header=header, encoding="utf-8")

    [read] = read_export(content)

    assert (read.note, read.amount, read.line) == ("Cena, cine y copas", Money(Decimal("-60.00"), "EUR"), 2)


def test_the_row_id_ignores_moneylovers_own_id() -> None:
    """Requirement detail: MoneyLover renumbers `Id` on every export, so it is not part of the stable id."""
    [first] = read_export(export(row(row_id="1")))
    [renumbered] = read_export(export(row(row_id="57")))

    assert first.external_id == renumbered.external_id
    assert first.external_id.startswith("ml:")


def test_identical_rows_get_distinct_ids() -> None:
    """Requirement detail: identical rows of one file stay distinct (two coffees on the same day)."""
    coffee = row(category="Comida y bebida", amount="-1.50", note="Café")
    first, second = read_export(export(coffee, coffee))

    assert first.external_id != second.external_id


@pytest.mark.usefixtures("bank_account")
def test_not_a_moneylover_export(client: TestClient) -> None:
    """Scenario: Not a MoneyLover export"""
    content = export(["1", "25/10/2026", "Gasolina", "-1.00", "EUR", ""], header=HEADER[:-1])

    response = client.post("/api/imports/preview", json=body(content, {}))

    assert (response.status_code, response.json()["detail"]) == (
        422,
        "No reconozco este fichero: falta la columna Cuenta",
    )


@pytest.mark.usefixtures("bank_account")
def test_unreadable_row(client: TestClient) -> None:
    """Scenario: Unreadable row"""
    content = export(row("01/02/2026"), row("31/02/2026"))

    response = client.post("/api/imports", json=body(content, {"Cuenta Principal": "new"}))

    assert response.status_code == 422
    assert "Línea 3" in response.json()["detail"]


# ---------- Stable identity of imported rows ----------


@pytest.mark.usefixtures("bank_account")
def test_newer_export(client: TestClient, db: Session) -> None:
    """Scenario: Newer export"""
    old = row("03/05/2025", "Gasolina", "-40.00", row_id="1")
    client.post("/api/imports", json=body(export(old), {"Cuenta Principal": "new"}))
    account_id = imported(db)[0].account_id
    newer = export(
        row("04/05/2025", "Gasolina", "-20.00", row_id="1"), row("03/05/2025", "Gasolina", "-40.00", row_id="2")
    )

    result = client.post("/api/imports", json=body(newer, {"Cuenta Principal": account_id})).json()

    assert (result["imported"], result["already_imported"]) == (1, 1)
    assert len(imported(db)) == 2


@pytest.mark.usefixtures("bank_account")
def test_identical_rows(client: TestClient, db: Session) -> None:
    """Scenario: Identical rows"""
    coffee = row("03/05/2025", "Comida y bebida", "-1.50", "Café")

    client.post("/api/imports", json=body(export(coffee, coffee), {"Cuenta Principal": "new"}))

    assert len(imported(db)) == 2


# ---------- Preview of an import ----------


def test_wallet_onto_a_bank_account(client: TestClient, db: Session, bank_account: int) -> None:
    """Scenario: Wallet onto a bank account"""
    content = export(
        row("25/10/2026"), row("01/07/2026"), row("30/06/2026"), row("05/05/2025"), row("10/05/2025", note="Ajuste")
    )

    result = preview(client, content, {"Cuenta Principal": bank_account})

    assert wallet(result, "Cuenta Principal") == {
        "name": "Cuenta Principal",
        "rows": 5,
        "first_date": "2025-05-05",
        "last_date": "2026-10-25",
        "target": bank_account,
        "to_import": 2,
        "skipped": 2,
        "bank_since": "2026-07-01",
        "already_imported": 0,
        "adjustments": 1,
    }
    assert imported(db) == []


@pytest.mark.usefixtures("bank_account")
def test_wallet_onto_a_new_account(client: TestClient, db: Session) -> None:
    """Scenario: Wallet onto a new account"""
    accounts_before = db.scalars(select(Account)).all()
    content = export(row("25/10/2026", wallet="Revolut"), row("05/05/2025", wallet="Revolut"))

    result = preview(client, content, {"Revolut": "new"})

    assert (wallet(result, "Revolut")["to_import"], wallet(result, "Revolut")["bank_since"]) == (2, None)
    db.expire_all()
    assert db.scalars(select(Account)).all() == accounts_before


@pytest.mark.usefixtures("bank_account")
def test_wallet_not_imported(client: TestClient) -> None:
    """Scenario: Wallet not imported"""
    content = export(row(wallet="Cuenta Ahorros"), row(wallet="Revolut"))

    result = preview(client, content, {"Revolut": "new"})

    assert (wallet(result, "Cuenta Ahorros")["rows"], wallet(result, "Cuenta Ahorros")["to_import"]) == (1, 0)
    assert wallet(result, "Cuenta Ahorros")["target"] is None


@pytest.mark.usefixtures("bank_account")
def test_unknown_account(client: TestClient) -> None:
    """Scenario: Unknown account"""
    response = client.post("/api/imports/preview", json=body(export(row()), {"Cuenta Principal": 9999}))

    assert response.status_code == 422


@pytest.mark.usefixtures("bank_account")
def test_file_too_large(client: TestClient) -> None:
    """Scenario: File too large"""
    response = client.post("/api/imports/preview", json=body(b"x" * (5 * 1024 * 1024 + 1), {}))

    assert response.status_code == 413


def test_imports_require_a_session(client: TestClient) -> None:
    """Requirement detail: like every other endpoint, imports need the session."""
    response = client.post("/api/imports/preview", json=body(export(row()), {}))

    assert response.status_code == 401


# ---------- Balance adjustments ----------


@pytest.mark.usefixtures("bank_account")
def test_adjustment_row(client: TestClient, db: Session) -> None:
    """Scenario: Adjustment row"""
    rows = [row(f"{day:02d}/05/2025") for day in range(1, 9)]
    content = export(*rows, row("09/05/2025", note="Ajuste"), row("10/05/2025", note=" ajuste "))

    result = preview(client, content, {"Cuenta Principal": "new"})
    client.post("/api/imports", json=body(content, {"Cuenta Principal": "new"}))

    assert (wallet(result, "Cuenta Principal")["to_import"], wallet(result, "Cuenta Principal")["adjustments"]) == (
        8,
        2,
    )
    assert len(imported(db)) == 8


# ---------- Importing ----------


@pytest.mark.usefixtures("bank_account")
def test_import_into_a_new_account(client: TestClient, db: Session) -> None:
    """Scenario: Import into a new account"""
    content = export(*(row(f"{day:02d}/05/2025", amount=f"-{day}.00", wallet="Revolut") for day in range(1, 29)))

    result = client.post("/api/imports", json=body(content, {"Revolut": "new"})).json()

    revolut = db.scalars(select(Account).where(Account.name == "Revolut")).one()
    assert (revolut.connection_id, revolut.role) == (None, "main")
    assert result == {"imported": 28, "skipped": 0, "already_imported": 0, "adjustments": 0}
    stored = imported(db)
    assert {t.account_id for t in stored} == {revolut.id} and len(stored) == 28
    may = client.get("/api/transactions", params={"month": "2025-05", "limit": 500}).json()
    assert len(may) == 28 and may[0]["account"] == "Revolut"


def test_import_onto_a_bank_account_skips_what_the_bank_has(client: TestClient, db: Session, bank_account: int) -> None:
    """Requirement detail: rows on or after the account's first bank transaction are not stored."""
    content = export(row("25/10/2026"), row("30/06/2026", note="Peaje"))

    result = client.post("/api/imports", json=body(content, {"Cuenta Principal": bank_account})).json()

    assert (result["imported"], result["skipped"]) == (1, 1)
    [stored] = imported(db)
    assert (stored.account_id, stored.booking_date, stored.description, stored.status) == (
        bank_account,
        date(2026, 6, 30),
        "Peaje",
        "BOOK",
    )


@pytest.mark.usefixtures("bank_account")
def test_import_twice(client: TestClient, db: Session) -> None:
    """Scenario: Import twice"""
    content = export(row("03/05/2025"), row("04/05/2025"))
    client.post("/api/imports", json=body(content, {"Cuenta Principal": "new"}))
    account_id = imported(db)[0].account_id

    result = client.post("/api/imports", json=body(content, {"Cuenta Principal": account_id})).json()

    assert (result["imported"], result["already_imported"]) == (0, 2)
    assert len(imported(db)) == 2


# ---------- Categories of imported rows ----------


def import_one(client: TestClient, db: Session, category: str, amount: str = "-8.80", note: str = "") -> Transaction:
    client.post(
        "/api/imports", json=body(export(row("03/05/2025", category, amount, note)), {"Cuenta Principal": "new"})
    )
    [transaction] = imported(db)
    return transaction


@pytest.mark.usefixtures("bank_account")
def test_built_in_category(client: TestClient, db: Session) -> None:
    """Scenario: Built-in category"""
    transaction = import_one(client, db, "Comer en casa o fuera", note="Churros")

    assert (category_of(db, transaction), transaction.category_manual) == ("Restaurantes", True)
    assert transaction.description == "Churros"


@pytest.mark.usefixtures("bank_account")
def test_same_name(client: TestClient, db: Session) -> None:
    """Scenario: Same name"""
    transaction = import_one(client, db, "OTROS GASTOS")

    assert (category_of(db, transaction), transaction.category_manual) == ("Otros gastos", True)
    assert transaction.description == "OTROS GASTOS"


@pytest.mark.usefixtures("bank_account")
def test_own_category(client: TestClient, db: Session) -> None:
    """Scenario: Own category"""
    supermarket = db.scalars(select(Category.id).where(Category.name == "Supermercado")).one()
    client.post("/api/rules", json={"pattern": "mercadona", "category_id": supermarket})

    transaction = import_one(client, db, "Deuda Coche Papá", note="Compra Mercadona")

    assert (category_of(db, transaction), transaction.category_manual) == ("Supermercado", False)


@pytest.mark.usefixtures("bank_account")
def test_moneylover_transfer(client: TestClient, db: Session) -> None:
    """Scenario: MoneyLover transfer"""
    transaction = import_one(client, db, "Transferencia entrante", amount="15.00", note="Bizum Toni")

    assert (transaction.kind, transaction.kind_manual) == ("normal", False)
    assert (category_of(db, transaction), transaction.category_manual) == ("Bizum recibido", False)


@pytest.mark.usefixtures("bank_account")
def test_unmatched_categories_are_listed(client: TestClient) -> None:
    """Requirement detail: the preview lists the categories without an equivalent, with their rows."""
    content = export(row(category="Ahorro"), row(category="Ahorro"), row(category="Invertir"), row(category="Gasolina"))

    result = preview(client, content, {})

    assert result["unmatched_categories"] == [{"name": "Ahorro", "rows": 2}, {"name": "Invertir", "rows": 1}]
