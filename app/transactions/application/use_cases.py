from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.shared.ids import AccountId, CategoryId, TransactionId
from app.transactions.application.ports import (
    CategoryCatalog,
    CategorySuggestions,
    MovementRecord,
    OwnAccounts,
    SearchCriteria,
    UnitOfWork,
)
from app.transactions.domain.errors import TransactionNotFound, UnknownCategory
from app.transactions.domain.transaction import Transaction


@dataclass(frozen=True)
class TransactionView:
    transaction: Transaction
    account_name: str


@dataclass(frozen=True)
class TransactionEdit:
    category_id: CategoryId | None = None
    clear_category: bool = False  # back to the automatic category
    kind: Literal["normal", "transfer"] | None = None
    note: str | None = None


@dataclass
class Ingest:
    """Stores the raw payloads fetched for one account and returns how many transactions are new."""

    uow: UnitOfWork
    own_accounts: OwnAccounts
    suggestions: CategorySuggestions

    def __call__(self, account_id: AccountId, raws: Sequence[dict[str, Any]]) -> int:
        with self.uow:
            # Pending transactions change their id once booked: drop them, the bank sends them again
            self.uow.transactions.delete_pending(account_id)
            ibans = self.own_accounts.ibans()
            suggester = self.suggestions.load()
            created = 0
            for raw in raws:
                incoming = Transaction.from_payload(account_id, raw)
                transaction = self.uow.transactions.by_external_id(account_id, incoming.external_id)
                if transaction is None:
                    transaction = incoming
                    created += 1
                else:
                    transaction.refresh_from(raw)
                transaction.derive(ibans, suggester)
                self.uow.transactions.save(transaction)
            self.uow.commit()
        return created


@dataclass
class ListMovements:
    uow: UnitOfWork

    def __call__(self, start: date | None = None, end: date | None = None) -> list[MovementRecord]:
        with self.uow:
            return self.uow.transactions.movement_records(start, end)


@dataclass
class LatestBookedDate:
    uow: UnitOfWork

    def __call__(self, account_id: AccountId) -> date | None:
        with self.uow:
            return self.uow.transactions.latest_booked_date(account_id)


@dataclass
class ReprocessAll:
    """Recomputes every transaction from its stored payload; manual categories and notes are kept."""

    uow: UnitOfWork
    own_accounts: OwnAccounts
    suggestions: CategorySuggestions

    def __call__(self) -> int:
        with self.uow:
            ibans = self.own_accounts.ibans()
            suggester = self.suggestions.load()
            transactions = self.uow.transactions.all()
            for transaction in transactions:
                transaction.refresh_from(transaction.raw)
                transaction.derive(ibans, suggester)
                self.uow.transactions.save(transaction)
            self.uow.commit()
        return len(transactions)


@dataclass
class ListTransactions:
    uow: UnitOfWork
    own_accounts: OwnAccounts

    def __call__(self, criteria: SearchCriteria) -> list[TransactionView]:
        with self.uow:
            found = self.uow.transactions.search(criteria)
        names = self.own_accounts.display_names({t.account_id for t in found})
        return [TransactionView(t, names.get(t.account_id, "")) for t in found]


@dataclass
class EditTransaction:
    uow: UnitOfWork
    own_accounts: OwnAccounts
    catalog: CategoryCatalog
    suggestions: CategorySuggestions
    reprocess_all: ReprocessAll

    def __call__(self, transaction_id: TransactionId, edit: TransactionEdit) -> TransactionView:
        with self.uow:
            transaction = self.uow.transactions.by_id(transaction_id)
            if transaction is None:
                raise TransactionNotFound()
            if edit.category_id is not None:
                if not self.catalog.exists(edit.category_id):
                    raise UnknownCategory()
                transaction.category_id = edit.category_id
                transaction.category_manual = True
            if edit.clear_category:
                transaction.category_manual = False
            if edit.kind is not None:
                transaction.set_kind(edit.kind, self.own_accounts.ibans(), self.suggestions.load())
            if edit.note is not None:
                transaction.note = edit.note or None
            self.uow.transactions.save(transaction)
            self.uow.commit()
        if edit.clear_category:
            self.reprocess_all()
            with self.uow:
                refreshed = self.uow.transactions.by_id(transaction_id)
            assert refreshed is not None
            transaction = refreshed
        names = self.own_accounts.display_names({transaction.account_id})
        return TransactionView(transaction, names.get(transaction.account_id, ""))


@dataclass(frozen=True)
class TransactionsServices:
    """The transactions use cases bound to one unit of work."""

    ingest: Ingest
    latest_booked_date: LatestBookedDate
    list_movements: ListMovements
    reprocess_all: ReprocessAll
    list_transactions: ListTransactions
    edit_transaction: EditTransaction
