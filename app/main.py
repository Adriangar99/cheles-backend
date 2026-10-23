import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app import stats
from app.bootstrap import Container, current, wire
from app.categorization.public import UnknownCategory
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.enablebanking import EnableBankingClient, EnableBankingError
from app.identity.public import AuthenticatedUser, require_user
from app.models import (
    Account,
    BankConnection,
    PendingAuth,
    Transaction,
)
from app.sync import normalize_iban, reprocess_all, sync_all, sync_connection

log = logging.getLogger("cheles")
settings = get_settings()


def scheduled_sync() -> None:
    with SessionLocal() as db:
        try:
            log.info("Sincronización programada: %s movimientos nuevos", sync_all(db))
        except Exception:
            log.exception("Falló la sincronización programada")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    current().categorization().seed_default_catalog()
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_sync, "cron", hour=settings.sync_hours)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Cheles", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
wire(app, Container.from_environment())


# ---------- Bancos ----------


def serialize_account(a: Account) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.alias or a.name,
        "iban_tail": a.iban[-4:] if a.iban else None,
        "currency": a.currency,
        "role": a.role,
        "balance": a.balance,
        "balance_at": a.balance_at,
        "connection_id": a.connection_id,
    }


def serialize_connection(c: BankConnection) -> dict[str, Any]:
    return {
        "id": c.id,
        "bank": c.aspsp_name,
        "status": c.status,
        "valid_until": c.valid_until,
        "last_synced_at": c.last_synced_at,
        "last_error": c.last_error,
        "accounts": [serialize_account(a) for a in c.accounts],
    }


@app.get("/api/banks", response_model=None)
def list_banks(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)) -> dict[str, Any]:
    connections = (
        db.scalars(select(BankConnection).options(joinedload(BankConnection.accounts)).order_by(BankConnection.id))
        .unique()
        .all()
    )
    orphans = db.scalars(select(Account).where(Account.connection_id.is_(None))).all()
    return {
        "connections": [serialize_connection(c) for c in connections],
        "detached_accounts": [serialize_account(a) for a in orphans],
    }


@app.get("/api/banks/available", response_model=None)
def available_banks(_: AuthenticatedUser = Depends(require_user)) -> list[dict[str, Any]]:
    try:
        aspsps = EnableBankingClient().list_aspsps(settings.eb_country)
    except EnableBankingError as e:
        raise HTTPException(502, f"Enable Banking: {e.body}") from e
    return [{"name": a["name"], "country": a["country"], "logo": a.get("logo")} for a in aspsps]


class ConnectBody(BaseModel):
    name: str
    country: str = settings.eb_country


@app.post("/api/banks/connect", response_model=None)
def connect_bank(
    body: ConnectBody, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    state = secrets.token_urlsafe(24)
    db.add(PendingAuth(state=state, aspsp_name=body.name, aspsp_country=body.country))
    db.commit()
    valid_until = datetime.now(UTC) + timedelta(days=settings.eb_consent_days)
    try:
        url = EnableBankingClient().start_auth(body.name, body.country, state, settings.eb_redirect_url, valid_until)
    except EnableBankingError as e:
        raise HTTPException(502, f"Enable Banking: {e.body}") from e
    return {"url": url}


@app.get("/api/banks/callback", response_model=None)
def bank_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_user),
) -> Response:
    def redirect(query: str) -> Response:
        return Response(status_code=303, headers={"Location": f"/bancos?{query}"})

    pending = db.get(PendingAuth, state) if state else None
    if error or not code or not pending:
        return redirect("error=1")

    try:
        session = EnableBankingClient().create_session(code)
    except EnableBankingError as e:
        log.warning("Error creando sesión: %s", e)
        return redirect("error=1")

    connection = BankConnection(
        aspsp_name=pending.aspsp_name,
        aspsp_country=pending.aspsp_country,
        session_id=session["session_id"],
        valid_until=datetime.fromisoformat(session["access"]["valid_until"]),
    )
    db.add(connection)
    db.flush()

    for acc in session["accounts"]:
        ident = acc.get("identification_hash")
        iban = normalize_iban((acc.get("account_id") or {}).get("iban"))
        # Si es una cuenta ya conocida (reconexión) la reenganchamos y conservamos su rol y alias
        account = db.scalar(select(Account).where(Account.identification_hash == ident)) if ident else None
        if account is None and iban:
            account = db.scalar(select(Account).where(Account.iban == iban))
        if account is None:
            account = Account(
                identification_hash=ident,
                name=acc.get("name") or pending.aspsp_name,
                currency=acc.get("currency") or "EUR",
            )
            db.add(account)
        account.connection_id = connection.id
        account.eb_uid = acc["uid"]
        account.iban = iban or account.iban
        account.identification_hash = ident or account.identification_hash

    db.delete(pending)
    db.commit()
    try:
        sync_connection(db, connection)
    except Exception:
        log.exception("Falló la primera sincronización")
    return redirect("connected=1")


@app.post("/api/banks/{connection_id}/sync", response_model=None)
def sync_one(
    connection_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    connection = db.get(BankConnection, connection_id)
    if not connection:
        raise HTTPException(404)
    return {"new": sync_connection(db, connection), "status": connection.status, "error": connection.last_error}


@app.post("/api/sync", response_model=None)
def sync_everything(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)) -> dict[str, Any]:
    return {"new": sync_all(db)}


@app.post("/api/reprocess", response_model=None)
def reprocess(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)) -> dict[str, Any]:
    return {"processed": reprocess_all(db)}


class AccountPatch(BaseModel):
    role: Literal["main", "savings", "excluded"] | None = None
    alias: str | None = None
    iban: str | None = None


@app.patch("/api/accounts/{account_id}", response_model=None)
def patch_account(
    account_id: int, body: AccountPatch, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404)
    changed_iban = False
    if body.role is not None:
        account.role = body.role
    if body.alias is not None:
        account.alias = body.alias or None
    if body.iban is not None:
        account.iban = normalize_iban(body.iban) or None
        changed_iban = True
    db.commit()
    if changed_iban:
        reprocess_all(db)
    return serialize_account(account)


# ---------- Movimientos y categorías ----------


def serialize_tx(t: Transaction) -> dict[str, Any]:
    return {
        "id": t.id,
        "date": t.booking_date,
        "amount": t.amount,
        "currency": t.currency,
        "status": t.status,
        "counterparty": t.counterparty,
        "description": t.description,
        "kind": t.kind,
        "category_id": t.category_id,
        "category_manual": t.category_manual,
        "account_id": t.account_id,
        "account": t.account.alias or t.account.name,
        "note": t.note,
    }


@app.get("/api/transactions", response_model=None)
def list_transactions(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    kind: Literal["normal", "transfer"] | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_user),
) -> list[dict[str, Any]]:
    stmt = select(Transaction).options(joinedload(Transaction.account))
    if month:
        start, end = stats.month_bounds(month)
        stmt = stmt.where(Transaction.booking_date >= start, Transaction.booking_date < end)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Transaction.counterparty.ilike(like), Transaction.description.ilike(like)))
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if kind:
        stmt = stmt.where(Transaction.kind == kind)
    stmt = stmt.order_by(Transaction.booking_date.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    return [serialize_tx(t) for t in db.scalars(stmt).unique()]


class TxPatch(BaseModel):
    category_id: int | None = None
    clear_category: bool = False  # volver a la categoría automática
    kind: Literal["normal", "transfer"] | None = None
    note: str | None = None


@app.patch("/api/transactions/{tx_id}", response_model=None)
def patch_transaction(
    tx_id: int, body: TxPatch, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404)
    if body.category_id is not None:
        if not current().categorization().category_exists(body.category_id):
            raise HTTPException(400, "Categoría inexistente")
        tx.category_id = body.category_id
        tx.category_manual = True
    if body.clear_category:
        tx.category_manual = False
    if body.kind is not None:
        tx.kind = body.kind
    if body.note is not None:
        tx.note = body.note or None
    db.commit()
    if body.clear_category:
        reprocess_all(db)
    return serialize_tx(tx)


class RuleBody(BaseModel):
    pattern: str
    category_id: int


@app.post("/api/rules", response_model=None)
def create_rule(
    body: RuleBody, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    """Creates a high-priority rule, then reprocesses so it applies to the whole history."""
    try:
        current().categorization().create_rule(body.pattern, body.category_id)
    except UnknownCategory:
        raise HTTPException(400, "Categoría inexistente") from None
    return {"processed": reprocess_all(db)}


# ---------- Estadísticas ----------


@app.get("/api/stats/summary", response_model=None)
def summary(
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    return {**stats.month_summary(db, month), "balances": stats.total_balance(db)}


@app.get("/api/stats/history", response_model=None)
def history(
    months: int = Query(12, le=60), db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_user)
) -> list[dict[str, Any]]:
    return stats.monthly_history(db, months)


@app.get("/api/health", response_model=None)
def health() -> dict[str, Any]:
    return {"ok": True}
