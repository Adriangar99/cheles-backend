import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app import stats
from app.categorize import seed_categories
from app.config import get_settings
from app.db import Base, SessionLocal, engine, get_db
from app.enablebanking import EnableBankingClient, EnableBankingError
from app.models import (
    Account,
    BankConnection,
    Category,
    PendingAuth,
    Rule,
    Transaction,
    User,
)
from app.security import (
    COOKIE_NAME,
    create_login_session,
    current_user,
    destroy_login_session,
    login_throttle,
    verify_password,
    verify_totp,
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
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_categories(db)
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_sync, "cron", hour=settings.sync_hours)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Cheles", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


# ---------- Auth ----------


class LoginBody(BaseModel):
    username: str
    password: str
    code: str


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    login_throttle.check(ip)
    user = db.scalar(select(User).where(User.username == body.username))
    # Se comprueba todo siempre, para no dar pistas de qué falló
    ok = bool(user) and verify_password(user.password_hash, body.password) and verify_totp(user.totp_secret, body.code)
    if not ok:
        login_throttle.fail(ip)
        raise HTTPException(401, "Datos incorrectos")
    login_throttle.reset(ip)
    token, expires_at = create_login_session(db, user)
    response.set_cookie(
        COOKIE_NAME,
        token,
        expires=expires_at,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        destroy_login_session(db, token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username}


# ---------- Bancos ----------


def serialize_account(a: Account) -> dict:
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


def serialize_connection(c: BankConnection) -> dict:
    return {
        "id": c.id,
        "bank": c.aspsp_name,
        "status": c.status,
        "valid_until": c.valid_until,
        "last_synced_at": c.last_synced_at,
        "last_error": c.last_error,
        "accounts": [serialize_account(a) for a in c.accounts],
    }


@app.get("/api/banks")
def list_banks(db: Session = Depends(get_db), _: User = Depends(current_user)):
    connections = db.scalars(select(BankConnection).options(joinedload(BankConnection.accounts)).order_by(BankConnection.id)).unique().all()
    orphans = db.scalars(select(Account).where(Account.connection_id.is_(None))).all()
    return {"connections": [serialize_connection(c) for c in connections], "detached_accounts": [serialize_account(a) for a in orphans]}


@app.get("/api/banks/available")
def available_banks(_: User = Depends(current_user)):
    try:
        aspsps = EnableBankingClient().list_aspsps(settings.eb_country)
    except EnableBankingError as e:
        raise HTTPException(502, f"Enable Banking: {e.body}")
    return [{"name": a["name"], "country": a["country"], "logo": a.get("logo")} for a in aspsps]


class ConnectBody(BaseModel):
    name: str
    country: str = settings.eb_country


@app.post("/api/banks/connect")
def connect_bank(body: ConnectBody, db: Session = Depends(get_db), _: User = Depends(current_user)):
    state = secrets.token_urlsafe(24)
    db.add(PendingAuth(state=state, aspsp_name=body.name, aspsp_country=body.country))
    db.commit()
    valid_until = datetime.now(timezone.utc) + timedelta(days=settings.eb_consent_days)
    try:
        url = EnableBankingClient().start_auth(body.name, body.country, state, settings.eb_redirect_url, valid_until)
    except EnableBankingError as e:
        raise HTTPException(502, f"Enable Banking: {e.body}")
    return {"url": url}


@app.get("/api/banks/callback")
def bank_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    redirect = lambda q: Response(status_code=303, headers={"Location": f"/bancos?{q}"})  # noqa: E731
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
            account = Account(identification_hash=ident, name=acc.get("name") or pending.aspsp_name, currency=acc.get("currency") or "EUR")
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


@app.post("/api/banks/{connection_id}/sync")
def sync_one(connection_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    connection = db.get(BankConnection, connection_id)
    if not connection:
        raise HTTPException(404)
    return {"new": sync_connection(db, connection), "status": connection.status, "error": connection.last_error}


@app.post("/api/sync")
def sync_everything(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return {"new": sync_all(db)}


@app.post("/api/reprocess")
def reprocess(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return {"processed": reprocess_all(db)}


class AccountPatch(BaseModel):
    role: Literal["main", "savings", "excluded"] | None = None
    alias: str | None = None
    iban: str | None = None


@app.patch("/api/accounts/{account_id}")
def patch_account(account_id: int, body: AccountPatch, db: Session = Depends(get_db), _: User = Depends(current_user)):
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


def serialize_tx(t: Transaction) -> dict:
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


@app.get("/api/transactions")
def list_transactions(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    kind: Literal["normal", "transfer"] | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
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


@app.patch("/api/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: TxPatch, db: Session = Depends(get_db), _: User = Depends(current_user)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404)
    if body.category_id is not None:
        if not db.get(Category, body.category_id):
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


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [
        {"id": c.id, "name": c.name, "kind": c.kind, "icon": c.icon, "color": c.color}
        for c in db.scalars(select(Category).order_by(Category.kind.desc(), Category.name))
    ]


class RuleBody(BaseModel):
    pattern: str
    category_id: int


@app.post("/api/rules")
def create_rule(body: RuleBody, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Crea una regla (con prioridad alta) y reprocesa para aplicarla a todo el histórico."""
    if not db.get(Category, body.category_id):
        raise HTTPException(400, "Categoría inexistente")
    db.add(Rule(pattern=body.pattern.strip(), category_id=body.category_id, priority=10))
    db.commit()
    return {"processed": reprocess_all(db)}


# ---------- Estadísticas ----------


@app.get("/api/stats/summary")
def summary(
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    return {**stats.month_summary(db, month), "balances": stats.total_balance(db)}


@app.get("/api/stats/history")
def history(months: int = Query(12, le=60), db: Session = Depends(get_db), _: User = Depends(current_user)):
    return stats.monthly_history(db, months)


@app.get("/api/health")
def health():
    return {"ok": True}
