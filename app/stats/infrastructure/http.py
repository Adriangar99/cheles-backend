"""FastAPI adapter for stats: the monthly summary and the history."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.http_types import JsonDecimal
from app.identity.public import AuthenticatedUser, require_user
from app.shared.year_month import YearMonth
from app.stats.application.use_cases import StatsServices
from app.stats.domain.figures import UNCATEGORIZED


def stats_services() -> StatsServices:
    """Placeholder dependency; the composition root (app.bootstrap.wire) overrides it with a real provider."""
    raise RuntimeError("Stats are not wired: call app.bootstrap.wire(app, container)")


class CategorySpendingOut(BaseModel):
    id: int | None  # null: spending without a category
    name: str
    icon: str
    color: str
    amount: JsonDecimal


class SummaryOut(BaseModel):
    month: str
    income: JsonDecimal
    expenses: JsonDecimal
    net: JsonDecimal
    saved: JsonDecimal
    by_category: list[CategorySpendingOut]
    balances: dict[str, JsonDecimal]  # by account role, plus "total"
    other_currencies: list[str]  # left out of every figure (only euros are counted)


class MonthTotalsOut(BaseModel):
    month: str
    income: JsonDecimal
    expenses: JsonDecimal


router = APIRouter()


@router.get("/api/stats/summary", response_model=SummaryOut)
def summary(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    services: StatsServices = Depends(stats_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    result = services.monthly_summary(YearMonth.parse(month) if month else None)
    figures = result.figures
    by_category = []
    for spending in figures.by_category:
        label = result.labels[spending.category_id]
        by_category.append(
            {
                "id": None if label is UNCATEGORIZED else spending.category_id,
                "name": label.name,
                "icon": label.icon,
                "color": label.color,
                "amount": spending.amount,
            }
        )
    return {
        "month": str(result.month),
        "income": figures.income,
        "expenses": figures.expenses,
        "net": figures.net,
        "saved": figures.saved,
        "by_category": by_category,
        "balances": result.balances,
        "other_currencies": result.other_currencies,
    }


@router.get("/api/stats/history", response_model=list[MonthTotalsOut])
def history(
    months: int = Query(12, le=60),
    services: StatsServices = Depends(stats_services),
    _: AuthenticatedUser = Depends(require_user),
) -> list[dict[str, Any]]:
    return [
        {"month": str(t.month), "income": t.income, "expenses": t.expenses} for t in services.monthly_history(months)
    ]
