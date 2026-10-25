import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.shared.ids import AccountId, CategoryId, TransactionId
from app.transactions.application.ports import (
    CategoryCatalog,
    CategoryNames,
    CategorySuggestions,
    ImportAccounts,
    MovementRecord,
    OwnAccounts,
    SearchCriteria,
    UnitOfWork,
)
from app.transactions.domain.errors import (
    TransactionNotFound,
    UndatedTransaction,
    UnknownCategory,
    UnknownImportTarget,
)
from app.transactions.domain.history_import import NEW, ImportPlan, Target, chosen_category, name_key, plan_import
from app.transactions.domain.moneylover import read_export
from app.transactions.domain.pending import matching_pending
from app.transactions.domain.transaction import Transaction

log = logging.getLogger(__name__)


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
            # Pending transactions change their id once booked: drop them (the bank sends them again), but keep them
            # at hand so the transaction that replaces each one inherits its manual edits
            removed_pending = self.uow.transactions.pop_pending(account_id)
            ibans = self.own_accounts.ibans()
            suggester = self.suggestions.load()
            created = 0
            for raw in raws:
                try:
                    incoming = Transaction.from_payload(account_id, raw)
                except UndatedTransaction:
                    reference = raw.get("entry_reference") or raw.get("transaction_id") or "sin referencia"
                    log.warning("Movimiento sin fecha ignorado (%s)", reference)
                    continue
                transaction = self.uow.transactions.by_external_id(account_id, incoming.external_id)
                if transaction is None:
                    transaction = incoming
                    created += 1
                    replaced = matching_pending(incoming, removed_pending)
                    if replaced is not None:
                        transaction.inherit_edits(replaced)
                        removed_pending.remove(replaced)
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
    """Recomputes every transaction from its stored payload; manual categories and notes are kept. Imported
    transactions have no bank payload: they stay as imported and only their derived fields are recomputed."""

    uow: UnitOfWork
    own_accounts: OwnAccounts
    suggestions: CategorySuggestions

    def __call__(self) -> int:
        with self.uow:
            ibans = self.own_accounts.ibans()
            suggester = self.suggestions.load()
            transactions = self.uow.transactions.all()
            for transaction in transactions:
                if transaction.source == "bank":
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
            if refreshed is None:
                raise TransactionNotFound()
            transaction = refreshed
        names = self.own_accounts.display_names({transaction.account_id})
        return TransactionView(transaction, names.get(transaction.account_id, ""))


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    already_imported: int
    adjustments: int


@dataclass
class PreviewImport:
    """What importing a MoneyLover export with these targets would do; writes nothing."""

    uow: UnitOfWork
    accounts: ImportAccounts
    categories: CategoryNames

    def __call__(self, content: bytes, targets: Mapping[str, Target]) -> ImportPlan:
        return _plan(self.uow, self.accounts, self.categories, content, targets)


@dataclass
class RunImport:
    """Imports a MoneyLover export: creates the new accounts, then stores the rows the plan imports."""

    uow: UnitOfWork
    accounts: ImportAccounts
    categories: CategoryNames
    suggestions: CategorySuggestions

    def __call__(self, content: bytes, targets: Mapping[str, Target]) -> ImportResult:
        plan = _plan(self.uow, self.accounts, self.categories, content, targets)
        catalog = {name_key(name): category_id for name, category_id in self.categories.ids_by_name().items()}
        with self.uow:
            suggester = self.suggestions.load()
            for wallet in plan.wallets:
                if wallet.target is None:
                    continue
                account_id = self.accounts.create_without_bank(wallet.name) if wallet.target == NEW else wallet.target
                for row in wallet.to_import:
                    chosen = chosen_category(row.category, catalog)
                    self.uow.transactions.save(Transaction.imported(account_id, row, chosen, suggester))
            self.uow.commit()
        return ImportResult(
            imported=sum(len(w.to_import) for w in plan.wallets),
            skipped=sum(w.skipped for w in plan.wallets),
            already_imported=sum(w.already_imported for w in plan.wallets),
            adjustments=sum(w.adjustments for w in plan.wallets),
        )


def _plan(
    uow: UnitOfWork, accounts: ImportAccounts, categories: CategoryNames, content: bytes, targets: Mapping[str, Target]
) -> ImportPlan:
    rows = read_export(content)
    existing = {target for target in targets.values() if target is not None and target != NEW}
    unknown = existing - set(accounts.display_names(existing))
    if unknown:
        raise UnknownImportTarget(f"La cuenta {min(unknown)} no existe")
    catalog = {name_key(name): category_id for name, category_id in categories.ids_by_name().items()}
    with uow:
        bank_since = {account_id: uow.transactions.earliest_bank_date(account_id) for account_id in existing}
        imported = {account_id: uow.transactions.imported_ids(account_id) for account_id in existing}
    return plan_import(rows, targets, bank_since, imported, catalog)


@dataclass(frozen=True)
class TransactionsServices:
    """The transactions use cases bound to one unit of work."""

    ingest: Ingest
    latest_booked_date: LatestBookedDate
    list_movements: ListMovements
    reprocess_all: ReprocessAll
    list_transactions: ListTransactions
    edit_transaction: EditTransaction
    preview_import: PreviewImport
    run_import: RunImport
