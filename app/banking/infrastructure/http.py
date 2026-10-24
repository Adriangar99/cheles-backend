"""FastAPI adapter for banking: connections, authorization flow, sync and account settings."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.banking.application.use_cases import BankingServices, ConnectionView
from app.banking.domain.account import Account
from app.banking.domain.errors import AccountNotFound, ConnectionNotFound, ProviderError, ProviderNotConfigured
from app.config import get_settings
from app.http_types import JsonDateTime, JsonDecimal
from app.identity.public import AuthenticatedUser, require_user
from app.shared.ids import AccountId


def banking_services() -> BankingServices:
    """Placeholder dependency; the composition root (app.bootstrap.wire) overrides it with a real provider."""
    raise RuntimeError("Banking is not wired: call app.bootstrap.wire(app, container)")


def serialize_account(a: Account) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.display_name,
        "iban_tail": a.iban.tail if a.iban else None,
        "currency": a.currency,
        "role": a.role,
        "balance": a.balance.amount if a.balance else None,
        "balance_at": a.balance_at,
        "connection_id": a.connection_id,
    }


def _serialize_connection(view: ConnectionView) -> dict[str, Any]:
    c = view.connection
    return {
        "id": c.id,
        "bank": c.aspsp_name,
        "status": c.status,
        "valid_until": c.valid_until,
        "last_synced_at": c.last_synced_at,
        "last_error": c.last_error,
        "accounts": [serialize_account(a) for a in view.accounts],
    }


class AccountOut(BaseModel):
    id: int
    name: str
    iban_tail: str | None
    currency: str
    role: Literal["main", "savings", "excluded"]
    balance: JsonDecimal | None
    balance_at: JsonDateTime | None
    connection_id: int | None


class ConnectionOut(BaseModel):
    id: int
    bank: str
    status: Literal["active", "expired", "revoked"]
    valid_until: JsonDateTime
    last_synced_at: JsonDateTime | None
    last_error: str | None
    accounts: list[AccountOut]


class BanksOut(BaseModel):
    connections: list[ConnectionOut]
    detached_accounts: list[AccountOut]


class AvailableBankOut(BaseModel):
    name: str
    country: str
    logo: str | None


class AuthorizationUrlOut(BaseModel):
    url: str


class SyncOut(BaseModel):
    new: int
    status: Literal["active", "expired", "revoked"]
    error: str | None


class SyncAllOut(BaseModel):
    new: int


def _provider_failure(error: ProviderError) -> HTTPException:
    return HTTPException(502, f"Enable Banking: {error.body}")


def _not_configured() -> HTTPException:
    return HTTPException(503, "Enable Banking no está configurado")


router = APIRouter()


@router.get("/api/banks", response_model=BanksOut)
def list_banks(
    services: BankingServices = Depends(banking_services), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    overview = services.list_connections()
    return {
        "connections": [_serialize_connection(view) for view in overview.connections],
        "detached_accounts": [serialize_account(a) for a in overview.detached_accounts],
    }


@router.get("/api/banks/available", response_model=list[AvailableBankOut])
def available_banks(
    services: BankingServices = Depends(banking_services), _: AuthenticatedUser = Depends(require_user)
) -> list[dict[str, Any]]:
    try:
        return services.list_available_banks()
    except ProviderError as e:
        raise _provider_failure(e) from e
    except ProviderNotConfigured:
        raise _not_configured() from None


class ConnectBody(BaseModel):
    name: str
    country: str = get_settings().eb_country


@router.post("/api/banks/connect", response_model=AuthorizationUrlOut)
def connect_bank(
    body: ConnectBody,
    services: BankingServices = Depends(banking_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    try:
        return {"url": services.start_authorization(body.name, body.country)}
    except ProviderError as e:
        raise _provider_failure(e) from e
    except ProviderNotConfigured:
        raise _not_configured() from None


@router.get("/api/banks/callback", response_model=None)
def bank_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    services: BankingServices = Depends(banking_services),
    _: AuthenticatedUser = Depends(require_user),
) -> Response:
    connected = services.complete_authorization(code, state, error)
    return Response(status_code=303, headers={"Location": f"/bancos?{'connected=1' if connected else 'error=1'}"})


@router.post("/api/banks/{connection_id}/sync", response_model=SyncOut)
def sync_one(
    connection_id: int,
    services: BankingServices = Depends(banking_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    try:
        result = services.sync_connection(connection_id)
    except ConnectionNotFound:
        raise HTTPException(404) from None
    except ProviderNotConfigured:
        raise _not_configured() from None
    return {"new": result.new, "status": result.status, "error": result.error}


@router.post("/api/sync", response_model=SyncAllOut)
def sync_everything(
    services: BankingServices = Depends(banking_services), _: AuthenticatedUser = Depends(require_user)
) -> dict[str, Any]:
    try:
        return {"new": services.sync_all()}
    except ProviderNotConfigured:
        raise _not_configured() from None


class AccountPatch(BaseModel):
    role: Literal["main", "savings", "excluded"] | None = None
    alias: str | None = None
    iban: str | None = None


@router.patch("/api/accounts/{account_id}", response_model=AccountOut)
def patch_account(
    account_id: int,
    body: AccountPatch,
    services: BankingServices = Depends(banking_services),
    _: AuthenticatedUser = Depends(require_user),
) -> dict[str, Any]:
    try:
        account = services.update_account(AccountId(account_id), body.role, body.alias, body.iban)
    except AccountNotFound:
        raise HTTPException(404) from None
    return serialize_account(account)
