from datetime import date, timedelta
from decimal import Decimal
from typing import Any

# Re-read this many days before the latest booked transaction, to catch late bookings
OVERLAP_DAYS = 10
BALANCE_PREFERENCE = ["ITAV", "CLAV", "XPCD", "ITBD", "CLBD"]


def window_start(latest_booked: date | None, today: date, initial_history_days: int) -> date:
    if latest_booked:
        return latest_booked - timedelta(days=OVERLAP_DAYS)
    return today - timedelta(days=initial_history_days)


def pick_balance(balances: list[dict[str, Any]]) -> Decimal | None:
    """The first balance type available by preference, else the first balance, else none."""
    by_type = {b.get("balance_type"): b for b in balances}
    for balance_type in BALANCE_PREFERENCE:
        if balance_type in by_type:
            return Decimal(by_type[balance_type]["balance_amount"]["amount"])
    return Decimal(balances[0]["balance_amount"]["amount"]) if balances else None
