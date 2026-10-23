from dataclasses import dataclass

from app.shared.events import Event
from app.shared.ids import AccountId


@dataclass(frozen=True)
class AccountIbanChanged(Event):
    """The IBAN of an own account was set or removed, so what counts as an own-account transfer may change."""

    account_id: AccountId
