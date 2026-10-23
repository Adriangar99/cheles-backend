from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Self

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.identity.domain.session import LoginSession
from app.identity.domain.user import User
from app.identity.infrastructure.orm import LoginSessionRow, UserRow


def _user(row: UserRow) -> User:
    return User(id=row.id, username=row.username, password_hash=row.password_hash, totp_secret=row.totp_secret)


class SqlUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_username(self, username: str) -> User | None:
        row = self.db.scalar(select(UserRow).where(UserRow.username == username))
        return _user(row) if row else None

    def by_id(self, user_id: int) -> User | None:
        row = self.db.get(UserRow, user_id)
        return _user(row) if row else None

    def add(self, user: User) -> None:
        row = UserRow(username=user.username, password_hash=user.password_hash, totp_secret=user.totp_secret)
        self.db.add(row)
        self.db.flush()
        user.id = row.id

    def delete_all(self) -> None:
        self.db.execute(delete(UserRow))


class SqlSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, session: LoginSession) -> None:
        self.db.add(
            LoginSessionRow(token_hash=session.token_hash, user_id=session.user_id, expires_at=session.expires_at)
        )

    def by_token_hash(self, token_hash: str) -> LoginSession | None:
        row = self.db.get(LoginSessionRow, token_hash)
        return LoginSession(row.token_hash, row.user_id, row.expires_at) if row else None

    def delete(self, token_hash: str) -> None:
        self.db.execute(delete(LoginSessionRow).where(LoginSessionRow.token_hash == token_hash))

    def delete_expired(self, now: datetime) -> None:
        self.db.execute(delete(LoginSessionRow).where(LoginSessionRow.expires_at < now))

    def delete_all(self) -> None:
        self.db.execute(delete(LoginSessionRow))


class SqlUnitOfWork:
    """A SQLAlchemy session per `with` block; anything not committed is rolled back when the block ends."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> Self:
        self.db = self.session_factory()
        self._users = SqlUserRepository(self.db)
        self._sessions = SqlSessionRepository(self.db)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.db.rollback()
        self.db.close()

    @property
    def users(self) -> SqlUserRepository:
        return self._users

    @property
    def sessions(self) -> SqlSessionRepository:
        return self._sessions

    def commit(self) -> None:
        self.db.commit()
