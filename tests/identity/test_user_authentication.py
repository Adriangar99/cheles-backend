"""Characterization of `identity/user-authentication`."""

import dataclasses
import getpass
import hashlib
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from typing import Any

import pyotp
import pytest
import qrcode
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.cli
import app.main
from app.bootstrap import Container, wire
from app.identity.application.ports import PasswordHasher, TotpService
from app.identity.infrastructure.orm import LoginSessionRow as LoginSession
from app.identity.infrastructure.orm import UserRow as User
from app.identity.infrastructure.security import SystemClock
from tests.helpers import PASSWORD, create_user, login

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def session_cookie(response: Any) -> str:
    header: str = response.headers["set-cookie"]
    return header


def cookie_token(response: Any) -> str:
    return session_cookie(response).split(";")[0].split("=", 1)[1]


def post_login(
    client: TestClient, code: str, username: str = "ana", password: str = PASSWORD, ip: str = "10.0.0.1"
) -> Any:
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password, "code": code},
        headers={"X-Test-Client-IP": ip},
    )


# ---------- Single user creation from the command line ----------


def run_create_user(monkeypatch: pytest.MonkeyPatch, username: str, *passwords: str) -> list[str]:
    """Calls the CLI command with scripted password prompts; returns the provisioning URIs put into the QR code."""
    answers = iter(passwords)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    uris: list[str] = []
    original_add_data = qrcode.QRCode.add_data

    def spy_add_data(self: Any, data: str, *args: Any, **kwargs: Any) -> None:
        uris.append(data)
        original_add_data(self, data, *args, **kwargs)

    monkeypatch.setattr(qrcode.QRCode, "add_data", spy_add_data)
    app.cli.create_user(username)
    return uris


def test_successful_creation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], db: Session) -> None:
    """Scenario: Successful creation"""
    uris = run_create_user(monkeypatch, "ana", PASSWORD, PASSWORD)

    users = db.scalars(select(User)).all()
    assert [u.username for u in users] == ["ana"]
    assert users[0].password_hash.startswith("$argon2")
    assert users[0].password_hash != PASSWORD
    output = capsys.readouterr().out
    assert f"Clave manual: {users[0].totp_secret}" in output
    assert len(uris) == 1
    assert uris[0] == pyotp.TOTP(users[0].totp_secret).provisioning_uri(name="ana", issuer_name="Cheles")


def test_replaces_the_previous_user(monkeypatch: pytest.MonkeyPatch, client: TestClient, db: Session) -> None:
    """Scenario: Replaces the previous user"""
    login(client, db, "ana")
    assert db.scalars(select(LoginSession)).all()

    run_create_user(monkeypatch, "bea", PASSWORD, PASSWORD)

    db.expire_all()
    assert [u.username for u in db.scalars(select(User))] == ["bea"]
    assert db.scalars(select(LoginSession)).all() == []


def test_password_too_short(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    """Scenario: Password too short"""
    create_user(db, "ana")

    with pytest.raises(SystemExit) as exit_info:
        run_create_user(monkeypatch, "bea", "short", "short")

    assert exit_info.value.code == "Demasiado corta."
    db.expire_all()
    assert [u.username for u in db.scalars(select(User))] == ["ana"]


def test_passwords_do_not_match(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    """Scenario: Passwords do not match"""
    create_user(db, "ana")

    with pytest.raises(SystemExit) as exit_info:
        run_create_user(monkeypatch, "bea", PASSWORD, PASSWORD + "!")

    assert exit_info.value.code == "No coinciden."
    db.expire_all()
    assert [u.username for u in db.scalars(select(User))] == ["ana"]


# ---------- Login with password and TOTP code ----------


def test_successful_login(client: TestClient, db: Session) -> None:
    """Scenario: Successful login"""
    secret = create_user(db)

    response = post_login(client, pyotp.TOTP(secret).now())

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert session_cookie(response).startswith("cheles_session=")


def test_totp_code_from_the_previous_period(client: TestClient, db: Session) -> None:
    """Scenario: TOTP code from the previous period"""
    secret = create_user(db)
    with time_machine.travel(NOW, tick=False):
        previous_code = pyotp.TOTP(secret).at(NOW - timedelta(seconds=30))

        response = post_login(client, f" {previous_code} ")

    assert response.status_code == 200


@pytest.mark.parametrize("wrong", ["user", "password", "code"])
def test_any_wrong_credential(client: TestClient, db: Session, wrong: str) -> None:
    """Scenario: Any wrong credential"""
    secret = create_user(db)
    code = pyotp.TOTP(secret).now()
    if wrong == "code":
        code = f"{(int(code) + 1) % 1_000_000:06d}"

    response = post_login(
        client,
        code,
        username="nobody" if wrong == "user" else "ana",
        password="wrong password" if wrong == "password" else PASSWORD,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Datos incorrectos"}


class CountingHasher:
    """The container's password hasher, counting verifications."""

    def __init__(self, inner: PasswordHasher) -> None:
        self.inner = inner
        self.verified = 0

    def hash(self, password: str) -> str:
        return self.inner.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        self.verified += 1
        return self.inner.verify(password_hash, password)


class CountingTotp:
    """The container's TOTP service, counting verifications."""

    def __init__(self, inner: TotpService) -> None:
        self.inner = inner
        self.verified = 0

    def new_secret(self) -> str:
        return self.inner.new_secret()

    def provisioning_uri(self, secret: str, username: str) -> str:
        return self.inner.provisioning_uri(secret, username)

    def verify(self, secret: str | None, code: str) -> bool:
        self.verified += 1
        return self.inner.verify(secret, code)


def test_same_work_for_every_failure(client: TestClient, db: Session, container: Container) -> None:
    """Scenario: Same work for every failure"""
    create_user(db)
    hasher = CountingHasher(container.hasher)
    totp = CountingTotp(container.totp)
    container.hasher, container.totp = hasher, totp

    post_login(client, "000000", username="nobody")
    assert (hasher.verified, totp.verified) == (1, 1)

    post_login(client, "000000", password="wrong password")
    assert (hasher.verified, totp.verified) == (2, 2)


# ---------- HttpOnly cookie session ----------


def test_session_cookie(client: TestClient, db: Session) -> None:
    """Scenario: Session cookie"""
    secret = create_user(db)
    with time_machine.travel(NOW, tick=False):
        response = post_login(client, pyotp.TOTP(secret).now())

    attributes = {part.strip().split("=")[0].lower(): part.strip() for part in session_cookie(response).split(";")}
    assert "httponly" in attributes
    assert attributes["samesite"].lower() == "samesite=lax"
    assert attributes["path"] == "Path=/"
    assert "secure" not in attributes
    expires = parsedate_to_datetime(attributes["expires"].split("=", 1)[1])
    assert expires == NOW + timedelta(days=14)


def test_the_token_is_not_stored_in_plain_text(client: TestClient, db: Session) -> None:
    """Scenario: The token is not stored in plain text"""
    secret = create_user(db)

    token = cookie_token(post_login(client, pyotp.TOTP(secret).now()))

    stored = [s.token_hash for s in db.scalars(select(LoginSession))]
    assert stored == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in stored


def test_expired_sessions_are_purged(client: TestClient, db: Session) -> None:
    """Scenario: Expired sessions are purged"""
    secret = create_user(db)
    user = db.scalars(select(User)).one()
    db.add(LoginSession(token_hash="old", user_id=user.id, expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()

    post_login(client, pyotp.TOTP(secret).now())

    db.expire_all()
    hashes = [s.token_hash for s in db.scalars(select(LoginSession))]
    assert "old" not in hashes
    assert len(hashes) == 1


# ---------- Session-protected endpoints ----------

PROTECTED = [
    ("GET", "/api/auth/me"),
    ("GET", "/api/banks"),
    ("GET", "/api/banks/available"),
    ("POST", "/api/banks/connect"),
    ("GET", "/api/banks/callback"),
    ("POST", "/api/banks/1/sync"),
    ("POST", "/api/sync"),
    ("POST", "/api/reprocess"),
    ("PATCH", "/api/accounts/1"),
    ("GET", "/api/transactions"),
    ("PATCH", "/api/transactions/1"),
    ("GET", "/api/categories"),
    ("POST", "/api/rules"),
    ("GET", "/api/stats/summary"),
    ("GET", "/api/stats/history"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_no_cookie(client: TestClient, method: str, path: str) -> None:
    """Scenario: No cookie"""
    response = client.request(method, path, json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


def test_expired_or_unknown_session(client: TestClient, db: Session) -> None:
    """Scenario: Expired or unknown session"""
    secret = create_user(db)
    token = cookie_token(post_login(client, pyotp.TOTP(secret).now()))
    client.cookies.clear()

    unknown = client.get("/api/auth/me", headers={"Cookie": "cheles_session=not-a-real-token"})
    with time_machine.travel(datetime.now(UTC) + timedelta(days=14, minutes=1)):
        expired = client.get("/api/auth/me", headers={"Cookie": f"cheles_session={token}"})
    still_valid = client.get("/api/auth/me", headers={"Cookie": f"cheles_session={token}"})

    assert (unknown.status_code, unknown.json()) == (401, {"detail": "No autenticado"})
    assert (expired.status_code, expired.json()) == (401, {"detail": "No autenticado"})
    assert still_valid.status_code == 200


def test_current_user(client: TestClient, db: Session) -> None:
    """Scenario: Current user"""
    login(client, db, "ana")

    response = client.get("/api/auth/me")

    assert response.json() == {"username": "ana"}


# ---------- Logout ----------


def test_logout_with_a_session(client: TestClient, db: Session) -> None:
    """Scenario: Logout with a session"""
    secret = create_user(db)
    token = cookie_token(post_login(client, pyotp.TOTP(secret).now()))

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert 'cheles_session=""' in session_cookie(response)
    assert "Max-Age=0" in session_cookie(response)
    assert db.scalars(select(LoginSession)).all() == []
    client.cookies.clear()
    assert client.get("/api/auth/me", headers={"Cookie": f"cheles_session={token}"}).status_code == 401


def test_logout_without_a_session(client: TestClient) -> None:
    """Scenario: Logout without a session"""
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------- Per-IP login attempt limit ----------


def fail_logins(client: TestClient, times: int, ip: str = "10.0.0.1") -> None:
    for _ in range(times):
        assert post_login(client, "000000", password="wrong password", ip=ip).status_code == 401


def test_blocked_after_5_failures(client: TestClient, db: Session) -> None:
    """Scenario: Blocked after 5 failures"""
    secret = create_user(db)
    fail_logins(client, 5)

    response = post_login(client, pyotp.TOTP(secret).now())

    assert response.status_code == 429
    assert response.json() == {"detail": "Demasiados intentos, espera unos minutos"}


def test_sliding_window(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: Sliding window"""
    clock = SimpleNamespace(now=1000.0)

    class SteppedClock(SystemClock):
        def monotonic(self) -> float:
            return float(clock.now)

    wire(app.main.app, dataclasses.replace(Container.from_environment(), clock=SteppedClock()))
    secret = create_user(db)
    fail_logins(client, 1)
    clock.now += 600
    fail_logins(client, 4)
    assert post_login(client, pyotp.TOTP(secret).now()).status_code == 429

    clock.now += 301  # the first failure is now more than 15 minutes old

    assert post_login(client, pyotp.TOTP(secret).now()).status_code == 200


def test_reset_after_a_successful_login(client: TestClient, db: Session) -> None:
    """Scenario: Reset after a successful login"""
    secret = create_user(db)
    fail_logins(client, 4)
    assert post_login(client, pyotp.TOTP(secret).now()).status_code == 200

    fail_logins(client, 4)

    assert post_login(client, "000000", password="wrong password").status_code == 401


def test_other_ips_are_not_affected(client: TestClient, db: Session) -> None:
    """Scenario: Other IPs are not affected"""
    secret = create_user(db)
    fail_logins(client, 5, ip="10.0.0.1")

    response = post_login(client, pyotp.TOTP(secret).now(), ip="10.0.0.2")

    assert response.status_code == 200
