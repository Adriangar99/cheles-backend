"""FastAPI adapter for transactions: listing, manual edits and reprocessing."""

import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.http_types import JsonDecimal
from app.identity.public import AuthenticatedUser, require_user
from app.shared.ids import AccountId, CategoryId, TransactionId
from app.shared.year_month import YearMonth
from app.transactions.application.ports import SearchCriteria
from app.transactions.application.use_cases import TransactionEdit, TransactionsServices, TransactionView
from app.transactions.domain.errors import TransactionNotFound, UnknownCategory


def transactions_services() -> TransactionsServices:
    """Placeholder dependency; the composition root (app.bootstrap.wire) overrides it with a real provider."""
    raise RuntimeError("Transactions are not wired: call app.bootstrap.wire(app, container)")


def _serialize(view: TransactionView) -> dict[str, Any]:
    t = view.transaction
    return {
        "id": t.id,
        "date": t.booking_date,
        "amount": t.amount.amount,
        "currency": t.amount.currency,
        "status": t.status,
        "counterparty": t.counterparty,
        "description": t.description,
        "kind": t.kind,
        "kind_manual": t.kind_manual,
        "category_id": t.category_id,
        "category_manual": t.category_manual,
        "account_id": t.account_id,
        "account": view.account_name,
        "note": t.note,
    }


class TransactionOut(BaseModel):
    id: int
    date: datetime.date
    amount: JsonDecimal  # signed: negative means money going out
    currency: str
    status: str
    counterparty: str | None
    description: str
    kind: Literal["normal", "transfer"]
    kind_manual: bool
    category_id: int | None
    category_manual: bool
    account_id: int
    account: str
    note: str | None


class ProcessedOut(BaseModel):
    processed: int


router = APIRouter()


@router.get("/api/transactions", response_model=list[TransactionOut])
def list_transactions(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    kind: Literal["normal", "transfer"] | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    services: TransactionsServices = Depends(transactions_services),
    _: AuthenticatedUser = Depends(require_user),
) -> list[dict[str, Any]]:
    criteria = SearchCriteria(
        month=YearMonth.parse(month) if month else None,
        text=q,
        category_id=CategoryId(category_id) if category_id is not None else None,
        account_id=AccountId(account_id) if account_id is not None else None,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return [_serialize(view) for view in services.list_transactions(criteria)]


class TxPatch(BaseModel):
    category_id: int | None = None
    clear_category: bool = False  # back to the automatic category
    kind: Literal["normal", "transfer"] | None = None
    note: str | None = None


@router.patch("/api/transactions/{tx_id}", response_model=TransactionOut)
def patch_transaction(
    tx_id: int,
    body: TxPatch,
    services: TransactionsServices = Depends(transactions_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    edit = TransactionEdit(
        category_id=CategoryId(body.category_id) if body.category_id is not None else None,
        clear_category=body.clear_category,
        kind=body.kind,
        note=body.note,
    )
    try:
        return _serialize(services.edit_transaction(TransactionId(tx_id), edit))
    except TransactionNotFound:
        raise HTTPException(404) from None
    except UnknownCategory:
        raise HTTPException(400, "Categoría inexistente") from None


@router.post("/api/reprocess", response_model=ProcessedOut)
def reprocess(
    services: TransactionsServices = Depends(transactions_services), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    return {"processed": services.reprocess_all()}
