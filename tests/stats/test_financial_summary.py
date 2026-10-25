"""Characterization of `stats/financial-summary`."""

from datetime import UTC, datetime
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.banking.infrastructure.orm import AccountRow as Account
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import balance, connect_bank, login, raw_tx

MAIN = "ES1111111111111111111111"
SAVINGS = "ES2222222222222222222222"
OTHER = "ES3333333333333333333333"


@pytest.fixture(autouse=True)
def october_2026() -> Any:
    with time_machine.travel(datetime(2026, 10, 23, 12, 0, tzinfo=UTC), tick=False):
        yield


@pytest.fixture
def bank(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> Any:
    """Connects main, savings and other accounts with the given raw transactions per account uid."""
    login(client, db)

    def run(roles: dict[str, str] | None = None, **transactions: list[dict[str, Any]]) -> None:
        fake_bank.transactions.update(transactions)
        connect_bank(
            client,
            fake_bank,
            [
                FakeAccount(uid="main", iban=MAIN),
                FakeAccount(uid="savings", iban=SAVINGS),
                FakeAccount(uid="other", iban=OTHER),
            ],
        )
        for uid, role in {"savings": "savings", **(roles or {})}.items():
            account_id = db.scalars(select(Account.id).where(Account.eb_uid == uid)).one()
            client.patch(f"/api/accounts/{account_id}", json={"role": role})

    return run


def summary(client: TestClient, month: str | None = "2026-10") -> dict[str, Any]:
    response = client.get("/api/stats/summary", params={"month": month} if month else {})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# ---------- Counted transactions ----------


def usd(amount: str, reference: str) -> dict[str, Any]:
    """A debit in dollars."""
    return raw_tx(amount, reference=reference, transaction_amount={"amount": amount, "currency": "USD"})


def connect_with_dollar_account(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """main (€1000), savings (€5000), excluded other (€200) and a main account in dollars ($300)."""
    login(client, db)
    fake_bank.balances.update(
        {
            "main": [balance("1000.00", "ITAV")],
            "savings": [balance("5000.00", "ITAV")],
            "other": [balance("200.00", "ITAV")],
            "usd": [balance("300.00", "ITAV")],
        }
    )
    connect_bank(
        client,
        fake_bank,
        [FakeAccount(uid=uid) for uid in ("main", "savings", "other")] + [FakeAccount(uid="usd", currency="USD")],
    )
    for uid, role in {"savings": "savings", "other": "excluded"}.items():
        account_id = db.scalars(select(Account.id).where(Account.eb_uid == uid)).one()
        client.patch(f"/api/accounts/{account_id}", json={"role": role})


def test_own_account_transfer(bank: Any, client: TestClient) -> None:
    """Scenario: Own-account transfer"""
    bank(
        main=[raw_tx("500.00", reference="out", creditor_iban=SAVINGS)],
        savings=[raw_tx("500.00", debit=False, reference="in", debtor_iban=MAIN)],
    )

    result = summary(client)

    assert (result["income"], result["expenses"]) == (0, 0)


def test_another_currency(bank: Any, client: TestClient) -> None:
    """Scenario: Another currency"""
    bank(main=[raw_tx("20.00", reference="eur", creditor="MERCADONA"), usd("40.00", "usd")])

    assert summary(client)["expenses"] == 20


def test_excluded_account(bank: Any, client: TestClient) -> None:
    """Scenario: Excluded account"""
    bank(roles={"other": "excluded"}, other=[raw_tx("30.00", reference="r1", creditor="MERCADONA")])

    assert summary(client)["expenses"] == 0


def test_pending_transaction(bank: Any, client: TestClient) -> None:
    """Scenario: Pending transaction"""
    bank(main=[raw_tx("20.00", transaction_id="p1", status="PDNG", creditor="MERCADONA")])

    assert summary(client)["expenses"] == 20


# ---------- Monthly summary ----------


def test_month_with_transactions(bank: Any, client: TestClient) -> None:
    """Scenario: Month with transactions"""
    bank(
        main=[
            raw_tx("2000.00", debit=False, reference="salary", booking_date="2026-09-28", remittance=["NOMINA"]),
            raw_tx("1000.00", reference="rent", booking_date="2026-09-01", remittance=["ALQUILER"]),
            raw_tx("200.00", reference="food", booking_date="2026-09-15", creditor="MERCADONA"),
            raw_tx("99.00", reference="october", booking_date="2026-10-01", creditor="MERCADONA"),
        ]
    )

    result = summary(client, "2026-09")

    assert (result["month"], result["income"], result["expenses"], result["net"]) == ("2026-09", 2000, 1200, 800)


def test_current_month_by_default(bank: Any, client: TestClient) -> None:
    """The month defaults to the current one (part of «Monthly summary»)."""
    bank(main=[raw_tx("10.00", reference="r1", booking_date="2026-10-02", creditor="MERCADONA")])

    result = summary(client, month=None)

    assert (result["month"], result["expenses"]) == ("2026-10", 10)


def test_month_without_transactions(bank: Any, client: TestClient) -> None:
    """Scenario: Month without transactions"""
    bank()

    result = summary(client, "2026-05")

    assert (result["income"], result["expenses"], result["net"]) == (0, 0, 0)


def test_malformed_month(client: TestClient, db: Session) -> None:
    """Scenario: Malformed month"""
    login(client, db)

    assert client.get("/api/stats/summary", params={"month": "09-2026"}).status_code == 422


# ---------- Monthly savings ----------


def test_contribution_to_savings(bank: Any, client: TestClient) -> None:
    """Scenario: Contribution to savings"""
    bank(
        main=[raw_tx("300.00", reference="out", creditor_iban=SAVINGS)],
        savings=[raw_tx("300.00", debit=False, reference="in", debtor_iban=MAIN)],
    )

    assert summary(client)["saved"] == 300


def test_withdrawal_from_savings(bank: Any, client: TestClient) -> None:
    """Scenario: Withdrawal from savings"""
    bank(
        savings=[
            raw_tx("300.00", debit=False, reference="in", debtor_iban=MAIN),
            raw_tx("500.00", reference="out", creditor_iban=MAIN),
        ]
    )

    assert summary(client)["saved"] == -200


# ---------- Spending by category ----------


def test_spending_breakdown(bank: Any, client: TestClient) -> None:
    """Scenario: Spending breakdown"""
    bank(
        main=[
            raw_tx("120.00", reference="r1", creditor="RESTAURANTE CASA PEPE"),
            raw_tx("100.00", reference="s1", creditor="MERCADONA"),
            raw_tx("200.00", reference="s2", creditor="LIDL"),
            raw_tx("2000.00", debit=False, reference="n1", remittance=["NOMINA"]),
        ]
    )

    by_category = summary(client)["by_category"]

    assert [(c["name"], c["amount"]) for c in by_category] == [("Supermercado", 300), ("Restaurantes", 120)]
    assert set(by_category[0]) == {"id", "name", "icon", "color", "amount"}


def test_uncategorized_debit(bank: Any, client: TestClient, db: Session) -> None:
    """Scenario: Uncategorized debit"""
    bank(main=[raw_tx("45.00", reference="r1", creditor="MERCADONA")])
    db.execute(update(Transaction).values(category_id=None))
    db.commit()

    assert summary(client)["by_category"] == [
        {"id": None, "name": "Sin categoría", "icon": "•", "color": "#8a8a8a", "amount": 45}
    ]


# ---------- Monthly history ----------


def month_of_activity(month: int) -> list[dict[str, Any]]:
    return [
        raw_tx("1000.00", debit=False, reference=f"in-{month}", booking_date=f"2026-{month:02d}-05", remittance=["X"]),
        raw_tx(f"{month}0.00", reference=f"out-{month}", booking_date=f"2026-{month:02d}-06", creditor="MERCADONA"),
    ]


def test_last_months(bank: Any, client: TestClient) -> None:
    """Scenario: Last months"""
    bank(main=[t for month in range(1, 10) for t in month_of_activity(month)])

    history = client.get("/api/stats/history", params={"months": 3}).json()

    assert history == [
        {"month": "2026-07", "income": 1000, "expenses": 70},
        {"month": "2026-08", "income": 1000, "expenses": 80},
        {"month": "2026-09", "income": 1000, "expenses": 90},
    ]


def test_history_defaults_to_12_months(bank: Any, client: TestClient) -> None:
    """The history covers 12 months by default (part of «Monthly history»)."""
    bank(main=[t for month in range(1, 10) for t in month_of_activity(month)])

    assert len(client.get("/api/stats/history").json()) == 9


def test_history_month_without_transactions(bank: Any, client: TestClient) -> None:
    """Scenario: Month without transactions"""
    bank(main=[t for month in (7, 9) for t in month_of_activity(month)])

    history = client.get("/api/stats/history").json()

    assert [h["month"] for h in history] == ["2026-07", "2026-09"]


def test_history_limit_exceeded(client: TestClient, db: Session) -> None:
    """Scenario: Limit exceeded"""
    login(client, db)

    assert client.get("/api/stats/history", params={"months": 61}).status_code == 422


# ---------- Balances by role ----------


def test_balances(bank: Any, client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Balances"""
    fake_bank.balances.update(
        {
            "main": [balance("1000.00", "ITAV")],
            "savings": [balance("5000.00", "ITAV")],
            "other": [balance("200.00", "ITAV")],
        }
    )
    bank(roles={"other": "excluded"})

    assert summary(client)["balances"] == {"main": 1000, "savings": 5000, "total": 6000}


def test_account_in_another_currency(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Account in another currency"""
    connect_with_dollar_account(client, db, fake_bank)

    assert summary(client)["balances"] == {"main": 1000, "savings": 5000, "total": 6000}


def test_roles_without_accounts_are_omitted(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Roles without accounts do not appear (part of «Balances by role»)."""
    login(client, db)
    fake_bank.balances["main"] = [balance("1000.00", "ITAV")]
    connect_bank(client, fake_bank, [FakeAccount(uid="main")])

    assert summary(client)["balances"] == {"main": 1000, "total": 1000}


# ---------- Amounts left out by currency ----------


def test_everything_in_euros(bank: Any, client: TestClient) -> None:
    """Scenario: Everything in euros"""
    bank(main=[raw_tx("20.00", reference="eur", creditor="MERCADONA")])

    assert summary(client)["other_currencies"] == []


def test_dollars_left_out(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Dollars left out"""
    connect_with_dollar_account(client, db, fake_bank)

    assert summary(client)["other_currencies"] == ["USD"]
