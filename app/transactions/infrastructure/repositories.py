from collections.abc import Callable
from datetime import date
from types import TracebackType
from typing import Self

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from app.shared.ids import AccountId, CategoryId, TransactionId
from app.shared.literals import parse_literal
from app.shared.money import Money
from app.transactions.application.ports import MovementRecord, SearchCriteria
from app.transactions.domain.transaction import BOOKED, KINDS, PENDING, SOURCES, Transaction
from app.transactions.infrastructure.orm import TransactionRow


def _entity(row: TransactionRow) -> Transaction:
    return Transaction(
        id=TransactionId(row.id),
        account_id=AccountId(row.account_id),
        external_id=row.external_id,
        booking_date=row.booking_date,
        amount=Money(row.amount, row.currency),
        status=row.status,
        counterparty=row.counterparty,
        counterparty_iban=row.counterparty_iban,
        description=row.description,
        raw=row.raw,
        source=parse_literal(row.source, SOURCES),
        kind=parse_literal(row.kind, KINDS),
        kind_manual=row.kind_manual,
        category_id=CategoryId(row.category_id) if row.category_id is not None else None,
        category_manual=row.category_manual,
        note=row.note,
    )


def _copy_to_row(transaction: Transaction, row: TransactionRow) -> None:
    row.account_id = transaction.account_id
    row.external_id = transaction.external_id
    row.booking_date = transaction.booking_date
    row.amount = transaction.amount.amount
    row.currency = transaction.amount.currency
    row.status = transaction.status
    row.counterparty = transaction.counterparty
    row.counterparty_iban = transaction.counterparty_iban
    row.description = transaction.description
    row.raw = transaction.raw
    row.source = transaction.source
    row.kind = transaction.kind
    row.kind_manual = transaction.kind_manual
    row.category_id = transaction.category_id
    row.category_manual = transaction.category_manual
    row.note = transaction.note


class SqlTransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_id(self, transaction_id: TransactionId) -> Transaction | None:
        row = self.db.get(TransactionRow, transaction_id)
        return _entity(row) if row else None

    def by_external_id(self, account_id: AccountId, external_id: str) -> Transaction | None:
        row = self.db.scalar(
            select(TransactionRow).where(
                TransactionRow.account_id == account_id, TransactionRow.external_id == external_id
            )
        )
        return _entity(row) if row else None

    def all(self) -> list[Transaction]:
        return [_entity(row) for row in self.db.scalars(select(TransactionRow))]

    def search(self, criteria: SearchCriteria) -> list[Transaction]:
        stmt: Select[tuple[TransactionRow]] = select(TransactionRow)
        if criteria.month:
            stmt = stmt.where(
                TransactionRow.booking_date >= criteria.month.start, TransactionRow.booking_date < criteria.month.end
            )
        if criteria.text:
            like = f"%{criteria.text}%"
            stmt = stmt.where(or_(TransactionRow.counterparty.ilike(like), TransactionRow.description.ilike(like)))
        if criteria.category_id:
            stmt = stmt.where(TransactionRow.category_id == criteria.category_id)
        if criteria.account_id:
            stmt = stmt.where(TransactionRow.account_id == criteria.account_id)
        if criteria.kind:
            stmt = stmt.where(TransactionRow.kind == criteria.kind)
        stmt = (
            stmt.order_by(TransactionRow.booking_date.desc(), TransactionRow.id.desc())
            .limit(criteria.limit)
            .offset(criteria.offset)
        )
        return [_entity(row) for row in self.db.scalars(stmt)]

    def latest_booked_date(self, account_id: AccountId) -> date | None:
        return self.db.scalar(
            select(func.max(TransactionRow.booking_date)).where(
                TransactionRow.account_id == account_id,
                TransactionRow.status == BOOKED,
                TransactionRow.source == "bank",
            )
        )

    def earliest_bank_date(self, account_id: AccountId) -> date | None:
        return self.db.scalar(
            select(func.min(TransactionRow.booking_date)).where(
                TransactionRow.account_id == account_id, TransactionRow.source == "bank"
            )
        )

    def imported_ids(self, account_id: AccountId) -> set[str]:
        return set(
            self.db.scalars(
                select(TransactionRow.external_id).where(
                    TransactionRow.account_id == account_id, TransactionRow.source == "import"
                )
            )
        )

    def movement_records(self, start: date | None, end: date | None) -> list[MovementRecord]:
        stmt = select(
            TransactionRow.account_id,
            TransactionRow.booking_date,
            TransactionRow.amount,
            TransactionRow.currency,
            TransactionRow.kind,
            TransactionRow.category_id,
        )
        if start:
            stmt = stmt.where(TransactionRow.booking_date >= start)
        if end:
            stmt = stmt.where(TransactionRow.booking_date < end)
        return [
            MovementRecord(
                account_id=AccountId(account_id),
                booking_date=booking_date,
                amount=amount,
                currency=currency,
                kind=parse_literal(kind, KINDS),
                category_id=CategoryId(category_id) if category_id is not None else None,
            )
            for account_id, booking_date, amount, currency, kind, category_id in self.db.execute(stmt)
        ]

    def pop_pending(self, account_id: AccountId) -> list[Transaction]:
        pending = (TransactionRow.account_id == account_id, TransactionRow.status == PENDING)
        removed = [_entity(row) for row in self.db.scalars(select(TransactionRow).where(*pending))]
        self.db.execute(delete(TransactionRow).where(*pending))
        return removed

    def save(self, transaction: Transaction) -> None:
        row = self.db.get(TransactionRow, transaction.id) if transaction.id is not None else None
        if row is None:
            row = TransactionRow()
            self.db.add(row)
        _copy_to_row(transaction, row)
        self.db.flush()
        transaction.id = TransactionId(row.id)


class SqlUnitOfWork:
    """A SQLAlchemy session per `with` block; anything not committed is rolled back when the block ends."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> Self:
        self.db = self.session_factory()
        self._transactions = SqlTransactionRepository(self.db)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.db.rollback()
        self.db.close()

    @property
    def transactions(self) -> SqlTransactionRepository:
        return self._transactions

    def commit(self) -> None:
        self.db.commit()
