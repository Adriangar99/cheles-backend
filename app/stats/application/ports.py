"""Where stats reads from; the composition root adapts other contexts' published read models to these ports."""

from collections.abc import Collection
from datetime import date
from typing import Protocol

from app.shared.ids import CategoryId
from app.stats.domain.figures import AccountStanding, Movement, SpendingLabel


class MovementsSource(Protocol):
    def between(self, start: date | None, end: date | None) -> list[Movement]:
        """Movements with `start <= booking_date < end` (either bound optional)."""
        ...


class AccountsSource(Protocol):
    def standings(self) -> list[AccountStanding]: ...


class CategoryLabelsSource(Protocol):
    def labels(self, category_ids: Collection[CategoryId]) -> dict[CategoryId, SpendingLabel]: ...


class Clock(Protocol):
    def today(self) -> date: ...
