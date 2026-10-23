"""Unit tests for the LogIn use case: the order of throttle, credential checks and session issuing."""

from datetime import timedelta

import pytest

from app.identity.application.use_cases import LogIn
from app.identity.domain.errors import InvalidCredentials, TooManyAttempts
from app.identity.domain.session import LoginSession, SessionToken
from app.identity.domain.throttle import LoginThrottle
from app.identity.domain.user import User
from tests.identity.in_memory import FakeClock, FixedTotp, InMemoryUnitOfWork, PlainHasher, SequentialTokens

IP = "10.0.0.1"


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    uow.users.add(User(username="ana", password_hash="hashed:secret password", totp_secret="S"))
    return uow


def log_in(uow: InMemoryUnitOfWork, throttle: LoginThrottle, clock: FakeClock, hasher: PlainHasher) -> LogIn:
    return LogIn(
        uow=uow,
        hasher=hasher,
        totp=FixedTotp(),
        clock=clock,
        tokens=SequentialTokens(),
        throttle=throttle,
        session_days=14,
    )


def test_the_throttle_is_checked_before_the_credentials(uow: InMemoryUnitOfWork) -> None:
    throttle, clock, hasher = LoginThrottle(), FakeClock(), PlainHasher()
    for _ in range(5):
        throttle.record_failure(IP, clock.monotonic())

    with pytest.raises(TooManyAttempts):
        log_in(uow, throttle, clock, hasher)("ana", "secret password", "123456", IP)

    assert hasher.verified == []
    assert uow.sessions.items == {}


@pytest.mark.parametrize(
    ("username", "password", "code"),
    [("nobody", "secret password", "123456"), ("ana", "wrong", "123456"), ("ana", "secret password", "000000")],
)
def test_wrong_credentials_record_a_failure(uow: InMemoryUnitOfWork, username: str, password: str, code: str) -> None:
    throttle, clock = LoginThrottle(limit=1), FakeClock()

    with pytest.raises(InvalidCredentials):
        log_in(uow, throttle, clock, PlainHasher())(username, password, code, IP)

    assert throttle.is_blocked(IP, clock.monotonic())
    assert uow.sessions.items == {}


def test_success_resets_the_throttle_purges_expired_sessions_and_stores_the_hashed_token(
    uow: InMemoryUnitOfWork,
) -> None:
    throttle, clock = LoginThrottle(), FakeClock()
    for _ in range(4):
        throttle.record_failure(IP, clock.monotonic())
    uow.sessions.add(LoginSession("old", user_id=1, expires_at=clock.now() - timedelta(seconds=1)))

    issued = log_in(uow, throttle, clock, PlainHasher())("ana", "secret password", "123456", IP)

    assert issued.token == SessionToken("token-1")
    assert issued.expires_at == clock.now() + timedelta(days=14)
    assert list(uow.sessions.items.values()) == [
        LoginSession(SessionToken("token-1").hashed(), user_id=1, expires_at=issued.expires_at)
    ]
    assert uow.commits == 1
    for _ in range(4):
        throttle.record_failure(IP, clock.monotonic())
    assert not throttle.is_blocked(IP, clock.monotonic())
