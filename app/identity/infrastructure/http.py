"""FastAPI adapter: the /api/auth routes and the dependency that requires an authenticated user."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.identity.application.use_cases import IdentityServices
from app.identity.domain.errors import InvalidCredentials, NotAuthenticated, TooManyAttempts
from app.identity.domain.session import SessionToken
from app.identity.domain.user import User

COOKIE_NAME = "cheles_session"


def identity_services() -> IdentityServices:
    """Placeholder dependency; the composition root (app.bootstrap.wire) overrides it with a real provider."""
    raise RuntimeError("Identity is not wired: call app.bootstrap.wire(app, container)")


def _session_token(request: Request) -> SessionToken | None:
    value = request.cookies.get(COOKIE_NAME)
    return SessionToken(value) if value else None


def require_user(request: Request, services: IdentityServices = Depends(identity_services)) -> User:
    try:
        return services.authenticate(_session_token(request))
    except NotAuthenticated:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado") from None


router = APIRouter(prefix="/api/auth")


class OkOut(BaseModel):
    ok: bool


class MeOut(BaseModel):
    username: str


class LoginBody(BaseModel):
    username: str
    password: str
    code: str


@router.post("/login", response_model=OkOut)
def login(
    body: LoginBody, request: Request, response: Response, services: IdentityServices = Depends(identity_services)
) -> dict[str, Any]:
    ip = request.client.host if request.client else "unknown"
    try:
        issued = services.log_in(body.username, body.password, body.code, ip)
    except TooManyAttempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos, espera unos minutos") from None
    except InvalidCredentials:
        # Same answer for every failure, to give no hint about what was wrong
        raise HTTPException(401, "Datos incorrectos") from None
    response.set_cookie(
        COOKIE_NAME,
        issued.token.value,
        expires=issued.expires_at,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"ok": True}


@router.post("/logout", response_model=OkOut)
def logout(
    request: Request, response: Response, services: IdentityServices = Depends(identity_services)
) -> dict[str, Any]:
    services.log_out(_session_token(request))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(require_user)) -> dict[str, Any]:
    return {"username": user.username}
