"""Characterization of `transactions/transaction-ingestion`."""

import hashlib
import itertools
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.infrastructure.orm import AccountRow as Account
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx

OWN_MAIN = "ES1111111111111111111111"
OWN_SAVINGS = "ES2222222222222222222222"


@pytest.fixture
def ingest(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> Any:
    """Stores the given raw transactions through a bank connection with two own accounts; returns them as rows."""
    login(client, db)
    codes = itertools.count()

    def run(*raws: dict[str, Any]) -> list[Transaction]:
        fake_bank.transactions["main"] = list(raws)
        connect_bank(
            client,
            fake_bank,
            [FakeAccount(uid="main", iban=OWN_MAIN), FakeAccount(uid="savings", iban=OWN_SAVINGS)],
            code=f"code-{next(codes)}",
        )
        return list(db.scalars(select(Transaction).order_by(Transaction.id)))

    return run


# ---------- Keeping the original transaction ----------


def test_raw_stored(ingest: Any) -> None:
    """Scenario: Raw stored"""
    raw = raw_tx("12.50", reference="r1", creditor="MERCADONA", remittance=["COMPRA"], bank_specific={"x": [1, 2]})

    [transaction] = ingest(raw)

    assert transaction.raw == raw


# ---------- Signed amount ----------


def test_debit(ingest: Any) -> None:
    """Scenario: Debit"""
    [transaction] = ingest(raw_tx("12.50", debit=True, reference="r1"))

    assert transaction.amount == Decimal("-12.50")


def test_credit(ingest: Any) -> None:
    """Scenario: Credit"""
    [transaction] = ingest(raw_tx("1500.00", debit=False, reference="r1"))

    assert transaction.amount == Decimal("1500.00")


def test_no_currency(ingest: Any) -> None:
    """Scenario: No currency"""
    raw = raw_tx("5.00", reference="r1")
    raw["transaction_amount"] = {"amount": "5.00"}

    [transaction] = ingest(raw)

    assert transaction.currency == "EUR"


# ---------- Transaction counterparty ----------


def test_counterparty_of_a_debit(ingest: Any) -> None:
    """Scenario: Counterparty of a debit"""
    [transaction] = ingest(raw_tx("12.50", reference="r1", creditor="MERCADONA", debtor="Ana"))

    assert transaction.counterparty == "MERCADONA"


def test_counterparty_of_a_credit(ingest: Any) -> None:
    """Scenario: Counterparty of a credit"""
    [transaction] = ingest(raw_tx("900.00", debit=False, reference="r1", debtor="EMPRESA SL", debtor_iban="es12 3456"))

    assert (transaction.counterparty, transaction.counterparty_iban) == ("EMPRESA SL", "ES123456")


def test_missing_counterparty_is_null(ingest: Any) -> None:
    """Missing counterparty name and IBAN are stored as null (part of «Transaction counterparty»)."""
    [transaction] = ingest(raw_tx("3.00", reference="r1"))

    assert (transaction.counterparty, transaction.counterparty_iban) == (None, None)


# ---------- Description, date and status ----------


def test_several_remittance_lines(ingest: Any) -> None:
    """Scenario: Several remittance lines"""
    [transaction] = ingest(raw_tx("3.00", reference="r1", remittance=["COMPRA TARJETA", "MERCADONA VALENCIA"]))

    assert transaction.description == "COMPRA TARJETA MERCADONA VALENCIA"


def test_no_remittance_information(ingest: Any) -> None:
    """Scenario: No remittance information"""
    [transaction] = ingest(raw_tx("3.00", reference="r1", bank_transaction_code={"description": "Recibo"}))

    assert transaction.description == "Recibo"


def test_description_is_truncated(ingest: Any) -> None:
    """Descriptions longer than 1024 characters are truncated (part of «Description, date and status»)."""
    [transaction] = ingest(raw_tx("3.00", reference="r1", remittance=["x" * 1500]))

    assert transaction.description == "x" * 1024


def test_no_booking_date(ingest: Any) -> None:
    """Scenario: No booking date"""
    [transaction] = ingest(raw_tx("3.00", reference="r1", booking_date=None, value_date="2026-10-05"))

    assert transaction.booking_date.isoformat() == "2026-10-05"


def test_pending_transaction(ingest: Any) -> None:
    """Scenario: Pending transaction"""
    [pending, default] = ingest(
        raw_tx("3.00", reference="r1", status="PDNG"), raw_tx("4.00", reference="r2", status=None)
    )

    assert (pending.status, default.status) == ("PDNG", "BOOK")


# ---------- Stable external id ----------


def test_with_a_bank_reference(ingest: Any) -> None:
    """Scenario: With a bank reference"""
    [transaction] = ingest(raw_tx("3.00", reference="ABC123", transaction_id="T9"))

    assert transaction.external_id == "ref:ABC123"


def test_only_a_transaction_id(ingest: Any) -> None:
    """Scenario: Only a transaction id"""
    [transaction] = ingest(raw_tx("3.00", transaction_id="T9"))

    assert transaction.external_id == "id:T9"


def test_no_bank_identifiers(ingest: Any) -> None:
    """Scenario: No bank identifiers"""
    long_text = "y" * 1500
    rows = ingest(
        raw_tx("3.00", booking_date="2026-10-03", remittance=[long_text]),
        raw_tx("3.00", booking_date="2026-10-03", remittance=[long_text]),
    )

    digest = hashlib.sha256(f"2026-10-03|-3.00|{long_text}".encode()).hexdigest()[:32]
    # Identical data gives the identical id, so the second payload updates the first instead of duplicating it
    assert [t.external_id for t in rows] == [f"h:{digest}"]


# ---------- Detecting transfers between own accounts ----------


def test_transfer_to_the_savings_account(ingest: Any) -> None:
    """Scenario: Transfer to the savings account"""
    [transaction] = ingest(raw_tx("300.00", reference="r1", creditor_iban="es22 2222 2222 2222 2222 2222"))

    assert (transaction.kind, transaction.category_id) == ("transfer", None)


@pytest.mark.parametrize("counterparty_iban", ["ES9999999999999999999999", None])
def test_payment_to_a_third_party(ingest: Any, counterparty_iban: str | None) -> None:
    """Scenario: Payment to a third party"""
    [transaction] = ingest(raw_tx("30.00", reference="r1", creditor="MERCADONA", creditor_iban=counterparty_iban))

    assert transaction.kind == "normal"
    assert transaction.category_id is not None


def test_excluded_account(ingest: Any, client: TestClient, db: Session) -> None:
    """Scenario: Excluded account"""
    ingest()
    excluded = db.scalars(select(Account).where(Account.eb_uid == "savings")).one()
    client.patch(f"/api/accounts/{excluded.id}", json={"role": "excluded"})

    [transaction] = ingest(raw_tx("50.00", reference="r1", creditor_iban=OWN_SAVINGS))

    assert transaction.kind == "transfer"
