"""What the identity use cases need from the outside world; infrastructure provides the implementations."""

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.identity.domain.session import LoginSession, SessionToken
from app.identity.domain.user import User


class UserRepository(Protocol):
    def by_username(self, username: str) -> User | None: ...

    def by_id(self, user_id: int) -> User | None: ...

    def add(self, user: User) -> None: ...

    def delete_all(self) -> None: ...


class SessionRepository(Protocol):
    def add(self, session: LoginSession) -> None: ...

    def by_token_hash(self, token_hash: str) -> LoginSession | None: ...

    def delete(self, token_hash: str) -> None: ...

    def delete_expired(self, now: datetime) -> None: ...

    def delete_all(self) -> None: ...


class UnitOfWork(Protocol):
    """One transaction: changes are kept only if `commit()` is called before leaving the block."""

    @property
    def users(self) -> UserRepository: ...

    @property
    def sessions(self) -> SessionRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None: ...

    def commit(self) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class TotpService(Protocol):
    def new_secret(self) -> str: ...

    def provisioning_uri(self, secret: str, username: str) -> str: ...

    def verify(self, secret: str, code: str) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime:
        """Wall-clock time, timezone-aware."""
        ...

    def monotonic(self) -> float:
        """Seconds for measuring intervals (the login throttle window)."""
        ...


class TokenGenerator(Protocol):
    def new_token(self) -> SessionToken: ...
