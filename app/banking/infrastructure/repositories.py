from collections.abc import Callable, Collection
from types import TracebackType
from typing import Self

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.banking.domain.account import ACCOUNT_ROLES, Account, Iban
from app.banking.domain.connection import CONNECTION_STATUSES, BankConnection, PendingAuthorization
from app.banking.infrastructure.orm import AccountRow, BankConnectionRow, PendingAuthRow
from app.shared.ids import AccountId
from app.shared.literals import parse_literal
from app.shared.money import Money


def _connection(row: BankConnectionRow) -> BankConnection:
    return BankConnection(
        id=row.id,
        aspsp_name=row.aspsp_name,
        aspsp_country=row.aspsp_country,
        session_id=row.session_id,
        valid_until=row.valid_until,
        status=parse_literal(row.status, CONNECTION_STATUSES),
        last_synced_at=row.last_synced_at,
        last_error=row.last_error,
    )


def _account(row: AccountRow) -> Account:
    return Account(
        id=AccountId(row.id),
        name=row.name,
        currency=row.currency,
        role=parse_literal(row.role, ACCOUNT_ROLES),
        alias=row.alias,
        iban=Iban(row.iban) if row.iban else None,
        connection_id=row.connection_id,
        eb_uid=row.eb_uid,
        identification_hash=row.identification_hash,
        balance=Money(row.balance, row.currency) if row.balance is not None else None,
        balance_at=row.balance_at,
    )


class SqlConnectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def all(self) -> list[BankConnection]:
        return [_connection(r) for r in self.db.scalars(select(BankConnectionRow).order_by(BankConnectionRow.id))]

    def active(self) -> list[BankConnection]:
        rows = self.db.scalars(select(BankConnectionRow).where(BankConnectionRow.status == "active"))
        return [_connection(r) for r in rows]

    def by_id(self, connection_id: int) -> BankConnection | None:
        row = self.db.get(BankConnectionRow, connection_id)
        return _connection(row) if row else None

    def save(self, connection: BankConnection) -> None:
        row = self.db.get(BankConnectionRow, connection.id) if connection.id is not None else None
        if row is None:
            row = BankConnectionRow()
            self.db.add(row)
        row.aspsp_name = connection.aspsp_name
        row.aspsp_country = connection.aspsp_country
        row.session_id = connection.session_id
        row.valid_until = connection.valid_until
        row.status = connection.status
        row.last_synced_at = connection.last_synced_at
        row.last_error = connection.last_error
        self.db.flush()
        connection.id = row.id


class SqlAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def all(self) -> list[Account]:
        return [_account(r) for r in self.db.scalars(select(AccountRow).order_by(AccountRow.id))]

    def of_connection(self, connection_id: int) -> list[Account]:
        rows = self.db.scalars(
            select(AccountRow).where(AccountRow.connection_id == connection_id).order_by(AccountRow.id)
        )
        return [_account(r) for r in rows]

    def detached(self) -> list[Account]:
        rows = self.db.scalars(select(AccountRow).where(AccountRow.connection_id.is_(None)).order_by(AccountRow.id))
        return [_account(r) for r in rows]

    def by_id(self, account_id: AccountId) -> Account | None:
        row = self.db.get(AccountRow, account_id)
        return _account(row) if row else None

    def by_ids(self, account_ids: Collection[AccountId]) -> list[Account]:
        return [_account(r) for r in self.db.scalars(select(AccountRow).where(AccountRow.id.in_(account_ids)))]

    def save(self, account: Account) -> None:
        row = self.db.get(AccountRow, account.id) if account.id is not None else None
        if row is None:
            row = AccountRow()
            self.db.add(row)
        row.connection_id = account.connection_id
        row.eb_uid = account.eb_uid
        row.identification_hash = account.identification_hash
        row.iban = account.iban.value if account.iban else None
        row.name = account.name
        row.alias = account.alias
        row.currency = account.currency
        row.role = account.role
        row.balance = account.balance.amount if account.balance else None
        row.balance_at = account.balance_at
        self.db.flush()
        account.id = AccountId(row.id)


class SqlPendingAuthorizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, pending: PendingAuthorization) -> None:
        self.db.add(
            PendingAuthRow(state=pending.state, aspsp_name=pending.aspsp_name, aspsp_country=pending.aspsp_country)
        )

    def get(self, state: str) -> PendingAuthorization | None:
        row = self.db.get(PendingAuthRow, state)
        return PendingAuthorization(row.state, row.aspsp_name, row.aspsp_country) if row else None

    def delete(self, state: str) -> None:
        self.db.execute(delete(PendingAuthRow).where(PendingAuthRow.state == state))


class SqlUnitOfWork:
    """A SQLAlchemy session per `with` block; anything not committed is rolled back when the block ends."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> Self:
        self.db = self.session_factory()
        self._connections = SqlConnectionRepository(self.db)
        self._accounts = SqlAccountRepository(self.db)
        self._pending = SqlPendingAuthorizationRepository(self.db)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.db.rollback()
        self.db.close()

    @property
    def connections(self) -> SqlConnectionRepository:
        return self._connections

    @property
    def accounts(self) -> SqlAccountRepository:
        return self._accounts

    @property
    def pending(self) -> SqlPendingAuthorizationRepository:
        return self._pending

    def commit(self) -> None:
        self.db.commit()
