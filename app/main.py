import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import legacy_stats as stats
from app.bootstrap import Container, current, wire
from app.categorization.public import UnknownCategory
from app.config import get_settings
from app.db import get_db
from app.identity.public import AuthenticatedUser, require_user
from app.shared.ids import CategoryId

log = logging.getLogger("cheles")
settings = get_settings()


def scheduled_sync() -> None:
    try:
        log.info("Sincronización programada: %s movimientos nuevos", current().banking().sync_all())
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


# ---------- Rules (orchestrated across categorization and transactions) ----------


class RuleBody(BaseModel):
    pattern: str
    category_id: int


@app.post("/api/rules", response_model=None)
def create_rule(body: RuleBody, _: AuthenticatedUser = Depends(require_user)) -> dict[str, Any]:
    """Creates a high-priority rule, then reprocesses so it applies to the whole history."""
    try:
        current().categorization().create_rule(body.pattern, CategoryId(body.category_id))
    except UnknownCategory:
        raise HTTPException(400, "Categoría inexistente") from None
    return {"processed": current().transactions().reprocess_all()}


# ---------- Stats ----------


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
