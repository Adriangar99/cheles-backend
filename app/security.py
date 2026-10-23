import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import LoginSession, User

COOKIE_NAME = "cheles_session"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_login_session(db: Session, user: User) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().session_days)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < datetime.now(timezone.utc)))
    db.add(LoginSession(token_hash=_hash_token(token), user_id=user.id, expires_at=expires_at))
    db.commit()
    return token, expires_at


def destroy_login_session(db: Session, token: str) -> None:
    db.execute(delete(LoginSession).where(LoginSession.token_hash == _hash_token(token)))
    db.commit()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = db.scalar(
            select(LoginSession).where(
                LoginSession.token_hash == _hash_token(token),
                LoginSession.expires_at > datetime.now(timezone.utc),
            )
        )
        if session:
            user = db.get(User, session.user_id)
            if user:
                return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")


class LoginThrottle:
    """Máximo `limit` intentos fallidos por IP en `window` segundos."""

    def __init__(self, limit: int = 5, window: int = 900):
        self.limit = limit
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        attempts = self._failures[key]
        while attempts and attempts[0] < time.monotonic() - self.window:
            attempts.popleft()
        return attempts

    def check(self, key: str) -> None:
        if len(self._prune(key)) >= self.limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos, espera unos minutos")

    def fail(self, key: str) -> None:
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_throttle = LoginThrottle()
