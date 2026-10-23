import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionToken:
    """The opaque value of the session cookie. Only its hash is ever stored."""

    value: str

    def hashed(self) -> str:
        return hashlib.sha256(self.value.encode()).hexdigest()


@dataclass
class LoginSession:
    token_hash: str
    user_id: int
    expires_at: datetime

    def is_active(self, now: datetime) -> bool:
        return self.expires_at > now
