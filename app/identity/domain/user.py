from dataclasses import dataclass

from app.identity.domain.errors import PasswordTooShort

MIN_PASSWORD_LENGTH = 12


@dataclass
class User:
    """The app's single user. `id` is None until the user is stored."""

    username: str
    password_hash: str
    totp_secret: str
    id: int | None = None


def ensure_valid_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShort()
