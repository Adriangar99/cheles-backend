from dataclasses import dataclass
from decimal import Decimal

from app.shared.ids import CategoryId
from app.shared.year_month import YearMonth
from app.stats.application.ports import AccountsSource, CategoryLabelsSource, Clock, MovementsSource
from app.stats.domain.figures import (
    UNCATEGORIZED,
    MonthFigures,
    MonthTotals,
    SpendingLabel,
    balances_by_role,
    history,
    month_figures,
)


@dataclass(frozen=True)
class Summary:
    month: YearMonth
    figures: MonthFigures
    labels: dict[CategoryId | None, SpendingLabel]
    balances: dict[str, Decimal]


@dataclass
class MonthlySummary:
    movements: MovementsSource
    accounts: AccountsSource
    labels: CategoryLabelsSource
    clock: Clock

    def __call__(self, month: YearMonth | None = None) -> Summary:
        if month is None:
            today = self.clock.today()
            month = YearMonth(today.year, today.month)
        standings = self.accounts.standings()
        figures = month_figures(month, self.movements.between(month.start, month.end), standings)
        ids = {s.category_id for s in figures.by_category if s.category_id is not None}
        known = self.labels.labels(ids)
        labels = {
            s.category_id: known.get(s.category_id, UNCATEGORIZED) if s.category_id is not None else UNCATEGORIZED
            for s in figures.by_category
        }
        return Summary(month, figures, labels, balances_by_role(standings))


@dataclass
class MonthlyHistory:
    movements: MovementsSource
    accounts: AccountsSource

    def __call__(self, months: int = 12) -> list[MonthTotals]:
        return history(self.movements.between(None, None), self.accounts.standings(), months)


@dataclass(frozen=True)
class StatsServices:
    monthly_summary: MonthlySummary
    monthly_history: MonthlyHistory
