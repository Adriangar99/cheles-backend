"""What the transactions use cases need from the outside world; infrastructure and the composition root provide it."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Literal, Protocol, Self

from app.shared.ids import AccountId, CategoryId, TransactionId
from app.shared.year_month import YearMonth
from app.transactions.domain.transaction import CategorySuggester, Transaction


@dataclass(frozen=True)
class SearchCriteria:
    month: YearMonth | None = None
    text: str | None = None
    category_id: CategoryId | None = None
    account_id: AccountId | None = None
    kind: Literal["normal", "transfer"] | None = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class MovementRecord:
    """Transactions' published read model: what other contexts may know about a movement."""

    account_id: AccountId
    booking_date: date
    amount: Decimal  # signed: negative means money going out
    kind: Literal["normal", "transfer"]
    category_id: CategoryId | None


class TransactionRepository(Protocol):
    def by_id(self, transaction_id: TransactionId) -> Transaction | None: ...

    def by_external_id(self, account_id: AccountId, external_id: str) -> Transaction | None: ...

    def all(self) -> list[Transaction]: ...

    def search(self, criteria: SearchCriteria) -> list[Transaction]:
        """Newest first (date, then id, descending)."""
        ...

    def latest_booked_date(self, account_id: AccountId) -> date | None: ...

    def movement_records(self, start: date | None, end: date | None) -> list[MovementRecord]:
        """Movements with `start <= booking_date < end` (either bound optional)."""
        ...

    def delete_pending(self, account_id: AccountId) -> None: ...

    def save(self, transaction: Transaction) -> None:
        """Inserts a new transaction (setting its `id`) or updates an existing one."""
        ...


class UnitOfWork(Protocol):
    """One transaction: changes are kept only if `commit()` is called before leaving the block."""

    @property
    def transactions(self) -> TransactionRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None: ...

    def commit(self) -> None: ...


class OwnAccounts(Protocol):
    """The user's own bank accounts, as transactions needs to see them."""

    def ibans(self) -> set[str]:
        """Normalized IBANs of every own account, whatever its role."""
        ...

    def display_names(self, account_ids: Collection[AccountId]) -> dict[AccountId, str]: ...


class CategorySuggestions(Protocol):
    def load(self) -> CategorySuggester:
        """A suggester with the current rules, to categorize many movements at once."""
        ...


class CategoryCatalog(Protocol):
    def exists(self, category_id: CategoryId) -> bool: ...
