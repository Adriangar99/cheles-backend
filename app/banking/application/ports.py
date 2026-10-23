"""What the banking use cases need from the outside world; infrastructure and the composition root provide it."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from types import TracebackType
from typing import Any, Protocol, Self

from app.banking.domain.account import Account
from app.banking.domain.connection import BankConnection, PendingAuthorization
from app.shared.ids import AccountId


@dataclass(frozen=True)
class BankingSettings:
    country: str
    consent_days: int
    redirect_url: str
    initial_history_days: int


class ConnectionRepository(Protocol):
    def all(self) -> list[BankConnection]:
        """Ordered by id."""
        ...

    def active(self) -> list[BankConnection]: ...

    def by_id(self, connection_id: int) -> BankConnection | None: ...

    def save(self, connection: BankConnection) -> None:
        """Inserts (setting `id`) or updates."""
        ...


class AccountRepository(Protocol):
    def all(self) -> list[Account]:
        """Ordered by id."""
        ...

    def of_connection(self, connection_id: int) -> list[Account]: ...

    def detached(self) -> list[Account]: ...

    def by_id(self, account_id: AccountId) -> Account | None: ...

    def by_ids(self, account_ids: Collection[AccountId]) -> list[Account]: ...

    def save(self, account: Account) -> None:
        """Inserts (setting `id`) or updates."""
        ...


class PendingAuthorizationRepository(Protocol):
    def add(self, pending: PendingAuthorization) -> None: ...

    def get(self, state: str) -> PendingAuthorization | None: ...

    def delete(self, state: str) -> None: ...


class UnitOfWork(Protocol):
    """One transaction: changes are kept only if `commit()` is called before leaving the block."""

    @property
    def connections(self) -> ConnectionRepository: ...

    @property
    def accounts(self) -> AccountRepository: ...

    @property
    def pending(self) -> PendingAuthorizationRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None: ...

    def commit(self) -> None: ...


class BankingProvider(Protocol):
    """Enable Banking, as banking needs it. Raises `ProviderError` on API errors."""

    def list_aspsps(self, country: str) -> list[dict[str, Any]]: ...

    def start_auth(
        self, aspsp_name: str, country: str, state: str, redirect_url: str, valid_until: datetime
    ) -> str: ...

    def create_session(self, code: str) -> dict[str, Any]: ...

    def get_balances(self, account_uid: str) -> list[dict[str, Any]]: ...

    def get_transactions(self, account_uid: str, date_from: date) -> list[dict[str, Any]]: ...


class TransactionsGateway(Protocol):
    """Where synced transactions go (the transactions context, through the composition root)."""

    def latest_booked_date(self, account_id: AccountId) -> date | None: ...

    def ingest(self, account_id: AccountId, raws: list[dict[str, Any]]) -> int: ...


class Clock(Protocol):
    def now(self) -> datetime:
        """Timezone-aware."""
        ...

    def today(self) -> date:
        """Local date."""
        ...


class StateGenerator(Protocol):
    def new_state(self) -> str: ...
