"""Adapters for the identity ports backed by argon2, pyotp and the standard library."""

import secrets
import time
from datetime import UTC, datetime

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.identity.domain.session import SessionToken

TOTP_ISSUER = "Cheles"


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False


class PyotpTotpService:
    def new_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, username: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=TOTP_ISSUER)

    def verify(self, secret: str, code: str) -> bool:
        # Accept the current 30 s period and one adjacent period
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class SecretsTokenGenerator:
    def new_token(self) -> SessionToken:
        return SessionToken(secrets.token_urlsafe(32))
