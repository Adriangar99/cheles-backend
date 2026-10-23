from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app import bootstrap
from app.categorization.public import CategoryLabel
from app.models import Account

# Transitional read-only exception (see [tool.importlinter]): stats aggregates the transactions table directly
# until stats becomes its own read model.
from app.transactions.infrastructure.orm import TransactionRow as Transaction


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    return start, end


def _counted[T: tuple[Any, ...]](stmt: Select[T]) -> Select[T]:
    """Solo movimientos que cuentan: no son transferencias propias y la cuenta no está excluida."""
    return stmt.join(Account, Account.id == Transaction.account_id).where(
        Transaction.kind == "normal", Account.role != "excluded"
    )


def _label(label: CategoryLabel | None) -> dict[str, Any]:
    """Spending without a category is shown as «Sin categoría» (a stats presentation choice)."""
    if label is None:
        return {"id": None, "name": "Sin categoría", "icon": "•", "color": "#8a8a8a"}
    return {"id": label.id, "name": label.name, "icon": label.icon, "color": label.color}


def month_summary(db: Session, month: str) -> dict[str, Any]:
    start, end = month_bounds(month)
    in_month = (Transaction.booking_date >= start, Transaction.booking_date < end)

    # coalesce(..., 0) never yields NULL
    income = cast(
        Decimal,
        db.scalar(
            _counted(select(func.coalesce(func.sum(Transaction.amount), 0))).where(*in_month, Transaction.amount > 0)
        ),
    )
    expenses = cast(
        Decimal,
        db.scalar(
            _counted(select(func.coalesce(func.sum(Transaction.amount), 0))).where(*in_month, Transaction.amount < 0)
        ),
    )

    # Ahorro del mes: lo que entra menos lo que sale de las cuentas de ahorro (transferencias propias)
    saved = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(Account, Account.id == Transaction.account_id)
        .where(*in_month, Transaction.kind == "transfer", Account.role == "savings")
    )

    spending_by_category = db.execute(
        _counted(select(Transaction.category_id, func.sum(Transaction.amount)))
        .where(*in_month, Transaction.amount < 0)
        .group_by(Transaction.category_id)
        .order_by(func.sum(Transaction.amount))
    ).all()
    labels = (
        bootstrap.current()
        .categorization()
        .category_labels({cid for cid, _ in spending_by_category if cid is not None})
    )

    return {
        "month": month,
        "income": income,
        "expenses": -expenses,
        "net": income + expenses,
        "saved": saved,
        "by_category": [
            {**_label(labels.get(cid) if cid is not None else None), "amount": -total}
            for cid, total in spending_by_category
        ],
    }


def monthly_history(db: Session, months: int = 12) -> list[dict[str, Any]]:
    month = func.to_char(Transaction.booking_date, "YYYY-MM")
    rows = db.execute(
        _counted(
            select(
                month.label("month"),
                func.coalesce(func.sum(Transaction.amount).filter(Transaction.amount > 0), 0),
                func.coalesce(func.sum(Transaction.amount).filter(Transaction.amount < 0), 0),
            )
        )
        .group_by(month)
        .order_by(month.desc())
        .limit(months)
    ).all()
    return [{"month": m, "income": i, "expenses": -e} for m, i, e in reversed(rows)]


def total_balance(db: Session) -> dict[str, Decimal]:
    rows = db.execute(
        select(Account.role, func.coalesce(func.sum(Account.balance), 0))
        .where(Account.role != "excluded")
        .group_by(Account.role)
    ).all()
    result = {role: total for role, total in rows}
    result["total"] = sum(result.values(), Decimal(0))
    return result
