"""Stats rules: which movements count and how monthly figures, history and balances are computed."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.shared.ids import AccountId, CategoryId
from app.shared.year_month import YearMonth

ZERO = Decimal(0)


@dataclass(frozen=True)
class Movement:
    """Stats' view of a bank movement."""

    account_id: AccountId
    booking_date: date
    amount: Decimal  # signed: negative means money going out
    kind: Literal["normal", "transfer"]
    category_id: CategoryId | None


@dataclass(frozen=True)
class AccountStanding:
    """Stats' view of an own account: whether it counts, whether it is savings, and its balance group."""

    account_id: AccountId
    counts: bool
    is_savings: bool
    balance_group: str
    balance: Decimal | None


@dataclass(frozen=True)
class SpendingLabel:
    """How a spending category is shown."""

    name: str
    icon: str
    color: str


# Spending without a category (a stats presentation choice)
UNCATEGORIZED = SpendingLabel(name="Sin categoría", icon="•", color="#8a8a8a")


@dataclass(frozen=True)
class CategorySpending:
    category_id: CategoryId | None
    amount: Decimal  # positive


@dataclass(frozen=True)
class MonthFigures:
    income: Decimal
    expenses: Decimal  # positive
    net: Decimal
    saved: Decimal
    by_category: list[CategorySpending]


@dataclass(frozen=True)
class MonthTotals:
    month: YearMonth
    income: Decimal
    expenses: Decimal  # positive


def _month_of(movement: Movement) -> YearMonth:
    return YearMonth(movement.booking_date.year, movement.booking_date.month)


def counted(movements: Iterable[Movement], standings: Sequence[AccountStanding]) -> list[Movement]:
    """Real income and expenses: not transfers between own accounts, and not from excluded accounts."""
    counting = {s.account_id for s in standings if s.counts}
    return [m for m in movements if m.kind == "normal" and m.account_id in counting]


def month_figures(
    month: YearMonth, movements: Iterable[Movement], standings: Sequence[AccountStanding]
) -> MonthFigures:
    in_month = [m for m in movements if month.start <= m.booking_date < month.end]
    real = counted(in_month, standings)
    income = sum((m.amount for m in real if m.amount > 0), ZERO)
    spent = sum((m.amount for m in real if m.amount < 0), ZERO)

    # Savings: what goes into savings accounts minus what leaves them (own-account transfers)
    savings = {s.account_id for s in standings if s.is_savings}
    saved = sum((m.amount for m in in_month if m.kind == "transfer" and m.account_id in savings), ZERO)

    by_category: dict[CategoryId | None, Decimal] = defaultdict(lambda: ZERO)
    for m in real:
        if m.amount < 0:
            by_category[m.category_id] += m.amount
    spending = sorted(by_category.items(), key=lambda item: item[1])  # most spent first
    return MonthFigures(
        income=income,
        expenses=-spent,
        net=income + spent,
        saved=saved,
        by_category=[CategorySpending(category_id, -total) for category_id, total in spending],
    )


def history(movements: Iterable[Movement], standings: Sequence[AccountStanding], months: int) -> list[MonthTotals]:
    """Income and expenses of the latest `months` months that have counted movements, oldest first."""
    income: dict[YearMonth, Decimal] = defaultdict(lambda: ZERO)
    spent: dict[YearMonth, Decimal] = defaultdict(lambda: ZERO)
    with_data: set[YearMonth] = set()
    for m in counted(movements, standings):
        month = _month_of(m)
        with_data.add(month)
        if m.amount > 0:
            income[month] += m.amount
        else:
            spent[month] += m.amount
    latest = sorted(with_data, reverse=True)[: max(months, 0)]
    return [MonthTotals(month, income[month], -spent[month]) for month in sorted(latest)]


def balances_by_role(standings: Sequence[AccountStanding]) -> dict[str, Decimal]:
    """Last known balance per balance group (missing balances as 0), excluded accounts left out, plus the total."""
    totals: dict[str, Decimal] = {}
    for s in standings:
        if s.counts:
            totals[s.balance_group] = totals.get(s.balance_group, ZERO) + (s.balance or ZERO)
    return {**totals, "total": sum(totals.values(), ZERO)}
