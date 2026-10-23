from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    return start, end


def _counted(stmt):
    """Solo movimientos que cuentan: no son transferencias propias y la cuenta no está excluida."""
    return stmt.join(Account, Account.id == Transaction.account_id).where(
        Transaction.kind == "normal", Account.role != "excluded"
    )


def month_summary(db: Session, month: str) -> dict:
    start, end = month_bounds(month)
    in_month = (Transaction.booking_date >= start, Transaction.booking_date < end)

    income = db.scalar(
        _counted(select(func.coalesce(func.sum(Transaction.amount), 0))).where(*in_month, Transaction.amount > 0)
    )
    expenses = db.scalar(
        _counted(select(func.coalesce(func.sum(Transaction.amount), 0))).where(*in_month, Transaction.amount < 0)
    )

    # Ahorro del mes: lo que entra menos lo que sale de las cuentas de ahorro (transferencias propias)
    saved = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(Account, Account.id == Transaction.account_id)
        .where(*in_month, Transaction.kind == "transfer", Account.role == "savings")
    )

    by_category = db.execute(
        _counted(
            select(Category.id, Category.name, Category.icon, Category.color, func.sum(Transaction.amount)).join(
                Category, Category.id == Transaction.category_id, isouter=True
            )
        )
        .where(*in_month, Transaction.amount < 0)
        .group_by(Category.id, Category.name, Category.icon, Category.color)
        .order_by(func.sum(Transaction.amount))
    ).all()

    return {
        "month": month,
        "income": income,
        "expenses": -expenses,
        "net": income + expenses,
        "saved": saved,
        "by_category": [
            {
                "id": cid,
                "name": name or "Sin categoría",
                "icon": icon or "•",
                "color": color or "#8a8a8a",
                "amount": -total,
            }
            for cid, name, icon, color, total in by_category
        ],
    }


def monthly_history(db: Session, months: int = 12) -> list[dict]:
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
