"""Unit tests for matching a received transaction with the pending one it replaces (pure domain)."""

from datetime import date
from decimal import Decimal

from app.shared.ids import AccountId, TransactionId
from app.shared.money import Money
from app.transactions.domain.pending import matching_pending
from app.transactions.domain.transaction import Transaction


def tx(
    external_id: str,
    day: int,
    *,
    amount: str = "-12.50",
    counterparty: str | None = "MERCADONA",
    description: str = "",
    id: int | None = None,
) -> Transaction:
    return Transaction(
        account_id=AccountId(1),
        external_id=external_id,
        booking_date=date(2026, 10, day),
        amount=Money(Decimal(amount), "EUR"),
        status="BOOK",
        counterparty=counterparty,
        counterparty_iban=None,
        description=description,
        raw={},
        id=TransactionId(id) if id is not None else None,
    )


def test_the_same_external_id_wins_over_a_closer_date() -> None:
    same_id = tx("x", 1, id=1)
    closer = tx("p2", 5, id=2)

    assert matching_pending(tx("x", 5), [closer, same_id]) is same_id


def test_the_closest_date_wins_then_the_lowest_id() -> None:
    two_days, one_day_late, one_day_early = tx("p1", 3, id=1), tx("p2", 6, id=3), tx("p3", 4, id=2)

    assert matching_pending(tx("b", 5), [two_days, one_day_late]) is one_day_late
    assert matching_pending(tx("b", 5), [two_days, one_day_late, one_day_early]) is one_day_early


def test_more_than_three_days_apart_does_not_match() -> None:
    assert matching_pending(tx("b", 8), [tx("p1", 4)]) is None
    assert matching_pending(tx("b", 7), [tx("p1", 4)]) is not None


def test_amount_and_counterparty_must_match() -> None:
    assert matching_pending(tx("b", 5), [tx("p1", 5, amount="-12.00")]) is None
    assert matching_pending(tx("b", 5), [tx("p1", 5, counterparty="LIDL")]) is None
    assert matching_pending(tx("b", 5, counterparty="mercadona"), [tx("p1", 5)]) is not None


def test_without_counterparty_the_description_must_match() -> None:
    pending = tx("p1", 5, counterparty=None, description="RECIBO LUZ")

    assert matching_pending(tx("b", 5, counterparty=None, description="recibo luz"), [pending]) is pending
    assert matching_pending(tx("b", 5, counterparty=None, description="RECIBO AGUA"), [pending]) is None
