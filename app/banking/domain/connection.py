from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.banking.domain.errors import ProviderError

ConnectionStatus = Literal["active", "expired", "revoked"]
LAST_ERROR_MAX_LENGTH = 1024


@dataclass(frozen=True)
class PendingAuthorization:
    """An authorization started with a bank and not completed yet (between /connect and the callback)."""

    state: str
    aspsp_name: str
    aspsp_country: str


@dataclass
class BankConnection:
    aspsp_name: str
    aspsp_country: str
    session_id: str
    valid_until: datetime
    status: ConnectionStatus = "active"
    last_synced_at: datetime | None = None
    last_error: str | None = None
    id: int | None = None

    def consent_expired(self, now: datetime) -> bool:
        return self.valid_until < now

    def record_sync_error(self, error: ProviderError) -> None:
        self.last_error = str(error)[:LAST_ERROR_MAX_LENGTH]
        if error.status_code in (401, 403):
            self.status = "expired"
