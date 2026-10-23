"""Unit tests for the stats aggregation rules (pure domain), mirroring the former SQL semantics."""

from datetime import date
from decimal import Decimal

from app.shared.ids import AccountId, CategoryId
from app.shared.year_month import YearMonth
from app.stats.domain.figures import (
    AccountStanding,
    Movement,
    balances_by_role,
    history,
    month_figures,
)

MAIN, SAVINGS, EXCLUDED = AccountId(1), AccountId(2), AccountId(3)
STANDINGS = [
    AccountStanding(MAIN, counts=True, is_savings=False, balance_group="main", balance=Decimal("1000")),
    AccountStanding(SAVINGS, counts=True, is_savings=True, balance_group="savings", balance=None),
    AccountStanding(EXCLUDED, counts=False, is_savings=False, balance_group="excluded", balance=Decimal("200")),
]
OCTOBER = YearMonth(2026, 10)


def mv(
    amount: str, day: str = "2026-10-05", account: AccountId = MAIN, kind: str = "normal", cat: int | None = 1
) -> Movement:
    return Movement(
        account_id=account,
        booking_date=date.fromisoformat(day),
        amount=Decimal(amount),
        kind="transfer" if kind == "transfer" else "normal",
        category_id=CategoryId(cat) if cat is not None else None,
    )


def test_only_normal_movements_of_counted_accounts_count() -> None:
    figures = month_figures(
        OCTOBER,
        [mv("2000"), mv("-50"), mv("-500", kind="transfer"), mv("-30", account=EXCLUDED)],
        STANDINGS,
    )

    assert (figures.income, figures.expenses, figures.net) == (Decimal("2000"), Decimal("50"), Decimal("1950"))


def test_only_movements_of_the_month_count() -> None:
    figures = month_figures(OCTOBER, [mv("-10", day="2026-09-30"), mv("-20", day="2026-11-01")], STANDINGS)

    assert (figures.income, figures.expenses, figures.net) == (Decimal(0), Decimal(0), Decimal(0))
    assert figures.by_category == []


def test_savings_is_the_net_of_transfers_on_savings_accounts() -> None:
    figures = month_figures(
        OCTOBER,
        [
            mv("300", account=SAVINGS, kind="transfer"),
            mv("-500", account=SAVINGS, kind="transfer"),
            mv("-300", kind="transfer"),
        ],
        STANDINGS,
    )

    assert figures.saved == Decimal("-200")


def test_spending_by_category_largest_first_with_an_uncategorized_group() -> None:
    figures = month_figures(
        OCTOBER,
        [mv("-120", cat=2), mv("-100", cat=1), mv("-200", cat=1), mv("-45", cat=None), mv("900", cat=3)],
        STANDINGS,
    )

    assert [(s.category_id, s.amount) for s in figures.by_category] == [
        (CategoryId(1), Decimal("300")),
        (CategoryId(2), Decimal("120")),
        (None, Decimal("45")),
    ]


def test_history_keeps_the_latest_months_with_data_in_chronological_order() -> None:
    movements = [mv("1000", day=f"2026-{m:02d}-05") for m in (1, 2, 3, 5)] + [mv("-40", day="2026-05-06")]

    result = history([*movements, mv("-1", day="2026-04-01", account=EXCLUDED)], STANDINGS, months=3)

    assert [(str(h.month), h.income, h.expenses) for h in result] == [
        ("2026-02", Decimal("1000"), Decimal("0")),
        ("2026-03", Decimal("1000"), Decimal("0")),
        ("2026-05", Decimal("1000"), Decimal("40")),
    ]


def test_balances_by_role() -> None:
    assert balances_by_role(STANDINGS) == {"main": Decimal("1000"), "savings": Decimal("0"), "total": Decimal("1000")}


def test_balances_omit_roles_without_accounts() -> None:
    assert balances_by_role(STANDINGS[:1]) == {"main": Decimal("1000"), "total": Decimal("1000")}
