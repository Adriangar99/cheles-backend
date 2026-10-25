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
        # Verified instead when there is no user, so an unknown username costs the same as a wrong password
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash or self._dummy_hash, password) and password_hash is not None
        except VerifyMismatchError:
            return False


class PyotpTotpService:
    def new_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, username: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=TOTP_ISSUER)

    def verify(self, secret: str | None, code: str) -> bool:
        # Accept the current 30 s period and one adjacent period; without a secret, check a random one (same work)
        valid = pyotp.TOTP(secret or pyotp.random_base32()).verify(code.strip(), valid_window=1)
        return valid and secret is not None


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class SecretsTokenGenerator:
    def new_token(self) -> SessionToken:
        return SessionToken(secrets.token_urlsafe(32))
