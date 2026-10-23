"""Unit tests for the YearMonth kernel value (strict format and month bounds)."""

from datetime import date

import pytest

from app.shared.year_month import YearMonth


def test_parses_a_valid_month() -> None:
    month = YearMonth.parse("2026-10")

    assert (month.year, month.month, str(month)) == (2026, 10, "2026-10")


@pytest.mark.parametrize("text", ["2026-9", "09-2026", "2026-13", "2026-00", "202610", ""])
def test_rejects_malformed_months(text: str) -> None:
    with pytest.raises(ValueError):
        YearMonth.parse(text)


def test_bounds_of_a_month() -> None:
    month = YearMonth.parse("2026-10")

    assert (month.start, month.end) == (date(2026, 10, 1), date(2026, 11, 1))


def test_december_ends_on_the_first_of_january() -> None:
    month = YearMonth.parse("2026-12")

    assert (month.start, month.end) == (date(2026, 12, 1), date(2027, 1, 1))
