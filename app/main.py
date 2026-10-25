"""Composition edge: the FastAPI app, its startup and scheduled jobs, and flows orchestrated across contexts."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.bootstrap import Container, wire
from app.categorization.public import EmptyRulePattern, UnknownCategory
from app.config import get_settings
from app.identity.public import AuthenticatedUser, require_user
from app.shared.ids import CategoryId

log = logging.getLogger("cheles")
settings = get_settings()


def _container() -> Container:
    container: Container = app.state.container
    return container


def scheduled_sync() -> None:
    try:
        log.info("Sincronización programada: %s movimientos nuevos", _container().banking().sync_all())
    except Exception:
        log.exception("Falló la sincronización programada")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _container().categorization().seed_default_catalog()
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_sync, "cron", hour=settings.sync_hours)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Cheles", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
wire(app, Container.from_environment())


class ProcessedOut(BaseModel):
    processed: int


class OkOut(BaseModel):
    ok: bool


class RuleBody(BaseModel):
    pattern: str
    category_id: int


@app.post("/api/rules", response_model=ProcessedOut)
def create_rule(body: RuleBody, request: Request, _: AuthenticatedUser = Depends(require_user)) -> dict[str, Any]:
    """Creates a high-priority rule in categorization, then reprocesses transactions so it applies to the history."""
    container: Container = request.app.state.container
    try:
        container.categorization().create_rule(body.pattern, CategoryId(body.category_id))
    except UnknownCategory:
        raise HTTPException(400, "Categoría inexistente") from None
    except EmptyRulePattern:
        raise HTTPException(400, "El patrón no puede estar vacío") from None
    return {"processed": container.transactions().reprocess_all()}


@app.get("/api/health", response_model=OkOut)
def health() -> dict[str, Any]:
    return {"ok": True}
