from dataclasses import dataclass
from datetime import datetime, timedelta

from app.identity.application.ports import Clock, PasswordHasher, TokenGenerator, TotpService, UnitOfWork
from app.identity.domain.errors import InvalidCredentials, NotAuthenticated, TooManyAttempts
from app.identity.domain.session import LoginSession, SessionToken
from app.identity.domain.throttle import LoginThrottle
from app.identity.domain.user import User, ensure_valid_password


@dataclass(frozen=True)
class IssuedSession:
    token: SessionToken
    expires_at: datetime


@dataclass(frozen=True)
class Provisioning:
    """What the user needs to set up their authenticator app."""

    secret: str
    uri: str


@dataclass
class LogIn:
    uow: UnitOfWork
    hasher: PasswordHasher
    totp: TotpService
    clock: Clock
    tokens: TokenGenerator
    throttle: LoginThrottle
    session_days: int

    def __call__(self, username: str, password: str, code: str, client_key: str) -> IssuedSession:
        if self.throttle.is_blocked(client_key, self.clock.monotonic()):
            raise TooManyAttempts()
        with self.uow:
            user = self.uow.users.by_username(username)
            if (
                user is None
                or user.id is None
                or not (self.hasher.verify(user.password_hash, password) and self.totp.verify(user.totp_secret, code))
            ):
                self.throttle.record_failure(client_key, self.clock.monotonic())
                raise InvalidCredentials()
            self.throttle.reset(client_key)

            now = self.clock.now()
            token = self.tokens.new_token()
            session = LoginSession(token.hashed(), user_id=user.id, expires_at=now + timedelta(days=self.session_days))
            self.uow.sessions.delete_expired(now)
            self.uow.sessions.add(session)
            self.uow.commit()
        return IssuedSession(token, session.expires_at)


@dataclass
class LogOut:
    uow: UnitOfWork

    def __call__(self, token: SessionToken | None) -> None:
        if token is None:
            return
        with self.uow:
            self.uow.sessions.delete(token.hashed())
            self.uow.commit()


@dataclass
class Authenticate:
    uow: UnitOfWork
    clock: Clock

    def __call__(self, token: SessionToken | None) -> User:
        if token is not None:
            with self.uow:
                session = self.uow.sessions.by_token_hash(token.hashed())
                if session is not None and session.is_active(self.clock.now()):
                    user = self.uow.users.by_id(session.user_id)
                    if user is not None:
                        return user
        raise NotAuthenticated()


@dataclass
class CreateUser:
    """Creates the app's single user, replacing any previous one and closing every session."""

    uow: UnitOfWork
    hasher: PasswordHasher
    totp: TotpService

    def __call__(self, username: str, password: str) -> Provisioning:
        ensure_valid_password(password)
        secret = self.totp.new_secret()
        with self.uow:
            self.uow.sessions.delete_all()
            self.uow.users.delete_all()
            self.uow.users.add(User(username=username, password_hash=self.hasher.hash(password), totp_secret=secret))
            self.uow.commit()
        return Provisioning(secret, self.totp.provisioning_uri(secret, username))
