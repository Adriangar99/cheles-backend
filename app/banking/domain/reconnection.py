from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.banking.domain.account import Account, Iban


@dataclass(frozen=True)
class IncomingAccount:
    """An account as an Enable Banking session lists it."""

    uid: str
    name: str | None
    currency: str | None
    identification_hash: str | None
    iban: Iban | None

    @classmethod
    def from_session(cls, payload: dict[str, Any]) -> "IncomingAccount":
        return cls(
            uid=payload["uid"],
            name=payload.get("name"),
            currency=payload.get("currency"),
            identification_hash=payload.get("identification_hash"),
            iban=Iban.parse((payload.get("account_id") or {}).get("iban")),
        )


def link_account(incoming: IncomingAccount, connection_id: int, bank_name: str, known: Sequence[Account]) -> Account:
    """Re-links a known account (by identification hash, then by IBAN) keeping its role, alias and history, or
    creates a new one."""
    account = next(
        (a for a in known if incoming.identification_hash and a.identification_hash == incoming.identification_hash),
        None,
    )
    if account is None and incoming.iban:
        account = next((a for a in known if a.iban == incoming.iban), None)
    if account is None:
        account = Account(
            identification_hash=incoming.identification_hash,
            name=incoming.name or bank_name,
            currency=incoming.currency or "EUR",
        )
    account.connection_id = connection_id
    account.eb_uid = incoming.uid
    account.iban = incoming.iban or account.iban
    account.identification_hash = incoming.identification_hash or account.identification_hash
    return account
