from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

from app.shared.ids import AccountId
from app.shared.money import Money

AccountRole = Literal["main", "savings", "excluded"]
ACCOUNT_ROLES: tuple[AccountRole, ...] = get_args(AccountRole)


@dataclass(frozen=True)
class Iban:
    """The IBAN of one of the user's own accounts (normalized). Identifies the account across reconnections.

    Banking-specific on purpose: transactions' counterparty IBAN means something else.
    """

    value: str

    @classmethod
    def parse(cls, raw: str | None) -> "Iban | None":
        normalized = raw.replace(" ", "").upper() if raw else ""
        return cls(normalized) if normalized else None

    @property
    def tail(self) -> str:
        return self.value[-4:]


@dataclass
class Account:
    name: str
    currency: str = "EUR"
    role: AccountRole = "main"
    alias: str | None = None
    iban: Iban | None = None
    connection_id: int | None = None
    # Enable Banking's uid changes on every reconnection; the identification hash is stable
    eb_uid: str | None = None
    identification_hash: str | None = None
    balance: Money | None = None
    balance_at: datetime | None = None
    id: AccountId | None = None

    @property
    def display_name(self) -> str:
        return self.alias or self.name

    def update(self, role: AccountRole | None, alias: str | None, iban: str | None) -> bool:
        """Applies the fields that were sent; returns whether the IBAN was set (even to the same value or empty)."""
        if role is not None:
            self.role = role
        if alias is not None:
            self.alias = alias or None
        if iban is not None:
            self.iban = Iban.parse(iban)
            return True
        return False
