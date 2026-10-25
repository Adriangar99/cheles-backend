"""Characterization of `categorization/transaction-categorization`."""

import itertools
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

import app.main
from app.categorization.infrastructure.orm import CategoryRow as Category
from app.categorization.infrastructure.orm import RuleRow as Rule
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx

EXPENSE = [
    "Supermercado",
    "Restaurantes",
    "Transporte",
    "Vivienda",
    "Suministros",
    "Suscripciones",
    "Compras",
    "Salud",
    "Ocio",
    "Viajes",
    "Impuestos y comisiones",
    "Efectivo",
    "Otros gastos",
]
INCOME = ["Nómina", "Bizum recibido", "Otros ingresos"]


@pytest.fixture
def categorize(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> Any:
    """Ingests raw transactions through a bank connection and returns the category name of each one."""
    login(client, db)
    codes = itertools.count()

    def run(*raws: dict[str, Any]) -> list[str | None]:
        fake_bank.transactions["u1"] = list(raws)
        connect_bank(client, fake_bank, [FakeAccount(uid="u1", identification_hash="h1")], code=f"c{next(codes)}")
        db.expire_all()
        rows = db.scalars(select(Transaction).order_by(Transaction.id)).all()
        names = {c.id: c.name for c in db.scalars(select(Category))}
        return [names.get(t.category_id) if t.category_id else None for t in rows]

    return run


def category_id(db: Session, name: str) -> int:
    found: int = db.scalars(select(Category.id).where(Category.name == name)).one()
    return found


# ---------- Default category and rule catalog ----------


def test_first_startup(db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: First startup"""
    db.execute(delete(Category))
    db.commit()

    with TestClient(app.main.app):
        pass

    categories = db.scalars(select(Category)).all()
    assert sorted(c.name for c in categories if c.kind == "expense") == sorted(EXPENSE)
    assert sorted(c.name for c in categories if c.kind == "income") == sorted(INCOME)
    rules = db.scalars(select(Rule)).all()
    assert {r.priority for r in rules} == {100}
    mercadona = next(r for r in rules if r.pattern == "mercadona")
    assert mercadona.category_id == category_id(db, "Supermercado")


def test_later_startups(db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Later startups"""
    db.add(Category(name="Mascotas", kind="expense", icon="🐾", color="#000000"))
    db.execute(delete(Rule).where(Rule.pattern == "mercadona"))
    db.commit()
    before = sorted((c.name, c.kind, c.icon, c.color) for c in db.scalars(select(Category)))
    rules_before = sorted((r.pattern, r.category_id, r.priority) for r in db.scalars(select(Rule)))

    with TestClient(app.main.app):
        pass

    db.expire_all()
    assert sorted((c.name, c.kind, c.icon, c.color) for c in db.scalars(select(Category))) == before
    assert sorted((r.pattern, r.category_id, r.priority) for r in db.scalars(select(Rule))) == rules_before


# ---------- Category listing ----------


def test_listing_order(client: TestClient, db: Session) -> None:
    """Scenario: Listing order"""
    login(client, db)

    categories = client.get("/api/categories").json()

    assert [c["name"] for c in categories] == sorted(INCOME) + sorted(EXPENSE)
    assert set(categories[0]) == {"id", "name", "kind", "icon", "color"}
    assert categories[0] == {
        "id": category_id(db, "Bizum recibido"),
        "name": "Bizum recibido",
        "kind": "income",
        "icon": "📲",
        "color": "#06d6a0",
    }


# ---------- Rule-based categorization ----------


def test_match_on_the_counterparty(categorize: Any) -> None:
    """Scenario: Match on the counterparty"""
    assert categorize(raw_tx("30.00", reference="r1", creditor="MERCADONA VALENCIA")) == ["Supermercado"]


def test_priority(categorize: Any, client: TestClient, db: Session) -> None:
    """Scenario: Priority"""
    categorize()
    client.post("/api/rules", json={"pattern": "mercadona", "category_id": category_id(db, "Ocio")})

    assert categorize(raw_tx("30.00", reference="r1", creditor="MERCADONA")) == ["Ocio"]


def test_rules_with_equal_priority_follow_creation_order(categorize: Any, client: TestClient, db: Session) -> None:
    """Equal priority falls back to creation order (part of «Rule-based categorization»)."""
    categorize()
    client.post("/api/rules", json={"pattern": "tienda", "category_id": category_id(db, "Ocio")})
    client.post("/api/rules", json={"pattern": "tienda", "category_id": category_id(db, "Salud")})

    assert categorize(raw_tx("30.00", reference="r1", creditor="TIENDA")) == ["Ocio"]


def test_patterns_with_a_trailing_space(categorize: Any) -> None:
    """Scenario: Patterns with a trailing space"""
    # «bar » (Restaurantes) does not match; «parking» (Transporte) does
    assert categorize(raw_tx("8.00", reference="r1", creditor="BARCELONA PARKING")) == ["Transporte"]


def test_expense_rule_on_an_income(categorize: Any) -> None:
    """Scenario: Expense rule on an income"""
    assert categorize(raw_tx("15.00", debit=False, reference="r1", debtor="MERCADONA")) == ["Supermercado"]


# ---------- Fallback categories ----------


def test_received_bizum(categorize: Any) -> None:
    """Scenario: Received Bizum"""
    assert categorize(raw_tx("20.00", debit=False, reference="r1", remittance=["BIZUM DE JUAN"])) == ["Bizum recibido"]


def test_other_income(categorize: Any) -> None:
    """Scenario: Other income"""
    assert categorize(raw_tx("20.00", debit=False, reference="r1", remittance=["DEVOLUCION"])) == ["Otros ingresos"]


def test_other_expense(categorize: Any) -> None:
    """Scenario: Other expense"""
    assert categorize(
        raw_tx("20.00", reference="r1", remittance=["CARGO DESCONOCIDO"]),
        raw_tx("0.00", debit=False, reference="r2", remittance=["AJUSTE"]),
    ) == ["Otros gastos", "Otros gastos"]


# ---------- User-created rules ----------


def test_new_rule(categorize: Any, client: TestClient, db: Session) -> None:
    """Scenario: New rule"""
    categorize(
        raw_tx("15.00", reference="auto", creditor="GASOLINERA PEPE"),
        raw_tx("20.00", reference="manual", creditor="GASOLINERA PEPE"),
    )
    manual = db.scalars(select(Transaction).where(Transaction.external_id == "ref:manual")).one()
    client.patch(f"/api/transactions/{manual.id}", json={"category_id": category_id(db, "Ocio")})
    transport = category_id(db, "Transporte")

    response = client.post("/api/rules", json={"pattern": "  gasolinera pepe  ", "category_id": transport})

    assert response.json() == {"processed": 2}
    rule = db.scalars(select(Rule).where(Rule.category_id == transport, Rule.priority == 10)).one()
    assert rule.pattern == "gasolinera pepe"
    db.expire_all()
    by_id = {c.id: c.name for c in db.scalars(select(Category))}
    names = [by_id[t.category_id] for t in db.scalars(select(Transaction).order_by(Transaction.id)) if t.category_id]
    assert names == ["Transporte", "Ocio"]


def test_unknown_category(client: TestClient, db: Session) -> None:
    """Scenario: Unknown category"""
    login(client, db)
    rules_before = len(db.scalars(select(Rule)).all())

    response = client.post("/api/rules", json={"pattern": "x", "category_id": 999})

    assert response.status_code == 400
    assert response.json() == {"detail": "Categoría inexistente"}
    assert len(db.scalars(select(Rule)).all()) == rules_before


def test_empty_pattern(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Empty pattern"""
    login(client, db)
    fake_bank.transactions["u1"] = [raw_tx("12.50", reference="r1", creditor="MERCADONA")]
    connect_bank(client, fake_bank, [FakeAccount(uid="u1")])
    # A category a reprocess would overwrite, so a reprocess would show
    leisure = db.scalars(select(Category.id).where(Category.name == "Ocio")).one()
    db.execute(update(Transaction).values(category_id=leisure))
    db.commit()
    rules_before = len(db.scalars(select(Rule)).all())

    response = client.post("/api/rules", json={"pattern": "   ", "category_id": leisure})

    assert response.status_code == 400
    assert response.json() == {"detail": "El patrón no puede estar vacío"}
    assert len(db.scalars(select(Rule)).all()) == rules_before
    db.expire_all()
    assert db.scalars(select(Transaction.category_id)).one() == leisure
