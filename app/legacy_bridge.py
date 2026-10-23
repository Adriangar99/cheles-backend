"""Adapters that let bounded contexts read legacy (not yet migrated) data through their own ports.

Only the composition root uses this module; contexts never import it. Each adapter disappears when the legacy code it
reads becomes a context with its own public API.
"""

from collections.abc import Callable, Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account
from app.shared.ids import AccountId


class LegacyOwnAccounts:
    """Transactions' `OwnAccounts` port over the legacy banking accounts."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def ibans(self) -> set[str]:
        with self.session_factory() as db:
            return {iban for iban in db.scalars(select(Account.iban)) if iban}

    def display_names(self, account_ids: Collection[AccountId]) -> dict[AccountId, str]:
        with self.session_factory() as db:
            accounts = db.scalars(select(Account).where(Account.id.in_(account_ids)))
            return {AccountId(a.id): a.alias or a.name for a in accounts}
