"""Characterization of `transactions/history-import`."""

from datetime import date
from decimal import Decimal

from app.shared.money import Money
from app.transactions.domain.moneylover import read_export
from tests.transactions.moneylover_export import HEADER, export, row

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
