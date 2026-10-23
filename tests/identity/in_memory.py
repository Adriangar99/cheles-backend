"""In-memory adapters for the identity ports, for unit tests of the use cases."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

from app.identity.domain.session import LoginSession, SessionToken
from app.identity.domain.user import User


@dataclass
class InMemoryUsers:
    items: dict[int, User] = field(default_factory=dict)

    def by_username(self, username: str) -> User | None:
        return next((u for u in self.items.values() if u.username == username), None)

    def by_id(self, user_id: int) -> User | None:
        return self.items.get(user_id)

    def add(self, user: User) -> None:
        user.id = user.id or max(self.items, default=0) + 1
        self.items[user.id] = user

    def delete_all(self) -> None:
        self.items.clear()


@dataclass
class InMemorySessions:
    items: dict[str, LoginSession] = field(default_factory=dict)

    def add(self, session: LoginSession) -> None:
        self.items[session.token_hash] = session

    def by_token_hash(self, token_hash: str) -> LoginSession | None:
        return self.items.get(token_hash)

    def delete(self, token_hash: str) -> None:
        self.items.pop(token_hash, None)

    def delete_expired(self, now: datetime) -> None:
        self.items = {k: s for k, s in self.items.items() if s.expires_at >= now}

    def delete_all(self) -> None:
        self.items.clear()


@dataclass
class InMemoryUnitOfWork:
    users: InMemoryUsers = field(default_factory=InMemoryUsers)
    sessions: InMemorySessions = field(default_factory=InMemorySessions)
    commits: int = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1


class PlainHasher:
    """Stores passwords as `hashed:<password>`; records verifications."""

    def __init__(self) -> None:
        self.verified: list[str] = []

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        self.verified.append(password)
        return password_hash == f"hashed:{password}"


class FixedTotp:
    """Accepts only the code `123456`."""

    def new_secret(self) -> str:
        return "SECRET"

    def provisioning_uri(self, secret: str, username: str) -> str:
        return f"otpauth://totp/Cheles:{username}?secret={secret}&issuer=Cheles"

    def verify(self, secret: str, code: str) -> bool:
        return code == "123456"


@dataclass
class FakeClock:
    wall: datetime = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    seconds: float = 1000.0

    def now(self) -> datetime:
        return self.wall

    def monotonic(self) -> float:
        return self.seconds


class SequentialTokens:
    def __init__(self) -> None:
        self.issued = 0

    def new_token(self) -> SessionToken:
        self.issued += 1
        return SessionToken(f"token-{self.issued}")
