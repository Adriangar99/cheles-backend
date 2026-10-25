"""FastAPI adapter for transactions: listing, manual edits, reprocessing and importing history."""

import base64
import binascii
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
from app.transactions.domain.errors import TransactionNotFound, UnknownCategory, UnknownImportTarget
from app.transactions.domain.history_import import NEW, ImportPlan, Target
from app.transactions.domain.moneylover import UnreadableRow, UnrecognizedFile

MAX_IMPORT_BYTES = 5 * 1024 * 1024


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


class ImportIn(BaseModel):
    file: str  # the CSV file, base64
    accounts: dict[str, int | Literal["new"] | None]  # wallet → existing account id, a new account, or not imported


class ImportWalletOut(BaseModel):
    name: str
    rows: int
    first_date: datetime.date
    last_date: datetime.date
    target: int | Literal["new"] | None
    to_import: int
    skipped: int  # on or after `bank_since`: the bank already has them
    bank_since: datetime.date | None
    already_imported: int
    adjustments: int  # balance corrections, never imported


class UnmatchedCategoryOut(BaseModel):
    name: str
    rows: int


class ImportPreviewOut(BaseModel):
    wallets: list[ImportWalletOut]
    unmatched_categories: list[UnmatchedCategoryOut]


class ImportResultOut(BaseModel):
    imported: int
    skipped: int
    already_imported: int
    adjustments: int


def _import_input(body: ImportIn) -> tuple[bytes, dict[str, Target]]:
    try:
        content = base64.b64decode(body.file, validate=True)
    except binascii.Error:
        raise HTTPException(422, "El fichero no se ha podido leer") from None
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "El fichero es demasiado grande (máximo 5 MB)")
    targets: dict[str, Target] = {
        wallet: NEW if target == NEW else AccountId(target) if target is not None else None
        for wallet, target in body.accounts.items()
    }
    return content, targets


def _rejected(error: Exception) -> HTTPException:
    return HTTPException(422, str(error))


def _serialize_plan(plan: ImportPlan) -> dict[str, Any]:
    return {
        "wallets": [
            {
                "name": w.name,
                "rows": len(w.rows),
                "first_date": w.first_date,
                "last_date": w.last_date,
                "target": w.target,
                "to_import": len(w.to_import),
                "skipped": w.skipped,
                "bank_since": w.bank_since,
                "already_imported": w.already_imported,
                "adjustments": w.adjustments,
            }
            for w in plan.wallets
        ],
        "unmatched_categories": [{"name": name, "rows": rows} for name, rows in plan.unmatched_categories],
    }


@router.post("/api/imports/preview", response_model=ImportPreviewOut)
def preview_import(
    body: ImportIn,
    services: TransactionsServices = Depends(transactions_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    content, targets = _import_input(body)
    try:
        return _serialize_plan(services.preview_import(content, targets))
    except (UnrecognizedFile, UnreadableRow, UnknownImportTarget) as error:
        raise _rejected(error) from None


@router.post("/api/imports", response_model=ImportResultOut)
def run_import(
    body: ImportIn,
    services: TransactionsServices = Depends(transactions_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    content, targets = _import_input(body)
    try:
        result = services.run_import(content, targets)
    except (UnrecognizedFile, UnreadableRow, UnknownImportTarget) as error:
        raise _rejected(error) from None
    return {
        "imported": result.imported,
        "skipped": result.skipped,
        "already_imported": result.already_imported,
        "adjustments": result.adjustments,
    }
