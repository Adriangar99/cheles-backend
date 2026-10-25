import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.banking.application.ports import (
    AccountSnapshot,
    BankingProvider,
    BankingSettings,
    Clock,
    StateGenerator,
    TransactionsGateway,
    UnitOfWork,
)
from app.banking.domain.account import Account, AccountRole
from app.banking.domain.connection import BankConnection, ConnectionStatus, PendingAuthorization
from app.banking.domain.errors import AccountNotFound, ConnectionNotFound, ProviderError, ProviderNotConfigured
from app.banking.domain.events import AccountIbanChanged
from app.banking.domain.reconnection import IncomingAccount, link_account
from app.banking.domain.sync_policy import pick_balance, window_start
from app.shared.events import EventPublisher
from app.shared.ids import AccountId, saved_id
from app.shared.money import Money

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConnectionView:
    connection: BankConnection
    accounts: list[Account]


@dataclass(frozen=True)
class BanksOverview:
    connections: list[ConnectionView]
    detached_accounts: list[Account]


@dataclass(frozen=True)
class SyncResult:
    new: int
    status: ConnectionStatus
    error: str | None


@dataclass
class ListConnections:
    uow: UnitOfWork

    def __call__(self) -> BanksOverview:
        with self.uow:
            return BanksOverview(
                connections=[
                    ConnectionView(c, self.uow.accounts.of_connection(c.id))
                    for c in self.uow.connections.all()
                    if c.id is not None and c.status != "revoked"
                ],
                detached_accounts=self.uow.accounts.detached(),
            )


@dataclass
class RemoveConnection:
    """Closes the bank session, revokes the connection and detaches its accounts (their transactions stay)."""

    uow: UnitOfWork
    provider: BankingProvider

    def __call__(self, connection_id: int) -> None:
        with self.uow:
            connection = self.uow.connections.by_id(connection_id)
            if connection is None:
                raise ConnectionNotFound()
            try:
                self.provider.delete_session(connection.session_id)
            except (ProviderError, ProviderNotConfigured) as error:
                # The user asked to remove it: do so locally even if the bank session could not be closed
                log.warning("No se pudo cerrar la sesión de %s: %s", connection.aspsp_name, error)
            connection.revoke()
            self.uow.connections.save(connection)
            for account in self.uow.accounts.of_connection(connection_id):
                account.detach()
                self.uow.accounts.save(account)
            self.uow.commit()


@dataclass
class ListAvailableBanks:
    provider: BankingProvider
    settings: BankingSettings

    def __call__(self) -> list[dict[str, Any]]:
        return [
            {"name": a["name"], "country": a["country"], "logo": a.get("logo")}
            for a in self.provider.list_aspsps(self.settings.country)
        ]


@dataclass
class StartAuthorization:
    """Records a pending authorization and returns the bank's authorization URL."""

    uow: UnitOfWork
    provider: BankingProvider
    settings: BankingSettings
    clock: Clock
    states: StateGenerator

    def __call__(self, bank_name: str, country: str) -> str:
        state = self.states.new_state()
        with self.uow:
            self.uow.pending.add(PendingAuthorization(state=state, aspsp_name=bank_name, aspsp_country=country))
            self.uow.commit()
        valid_until = self.clock.now() + timedelta(days=self.settings.consent_days)
        return self.provider.start_auth(bank_name, country, state, self.settings.redirect_url, valid_until)


@dataclass
class SyncConnection:
    uow: UnitOfWork
    provider: BankingProvider
    transactions: TransactionsGateway
    settings: BankingSettings
    clock: Clock

    def __call__(self, connection_id: int) -> SyncResult:
        with self.uow:
            connection = self.uow.connections.by_id(connection_id)
            if connection is None:
                raise ConnectionNotFound()
            # The bank already rejected (or the user removed) this consent: report it without calling the provider
            if connection.status != "active":
                return SyncResult(0, connection.status, connection.last_error)
            if connection.consent_expired(self.clock.now()):
                connection.status = "expired"
                self.uow.connections.save(connection)
                self.uow.commit()
                return SyncResult(0, connection.status, connection.last_error)
            total = 0
            try:
                for account in self.uow.accounts.of_connection(connection_id):
                    if account.eb_uid:
                        total += self._sync_account(account, account.eb_uid)
                connection.last_error = None
            except ProviderError as error:
                log.warning("Error sincronizando %s: %s", connection.aspsp_name, error)
                connection.record_sync_error(error)
            connection.last_synced_at = self.clock.now()
            self.uow.connections.save(connection)
            self.uow.commit()
            return SyncResult(total, connection.status, connection.last_error)

    def _sync_account(self, account: Account, eb_uid: str) -> int:
        account_id = saved_id(account.id, "Account")
        date_from = window_start(
            self.transactions.latest_booked_date(account_id), self.clock.today(), self.settings.initial_history_days
        )
        # Both provider calls happen before writing, so a failure stores nothing for this account
        raws = self.provider.get_transactions(eb_uid, date_from)
        balances = self.provider.get_balances(eb_uid)
        new = self.transactions.ingest(account_id, raws)
        amount = pick_balance(balances)
        account.balance = Money(amount, account.currency) if amount is not None else None
        account.balance_at = self.clock.now()
        self.uow.accounts.save(account)
        self.uow.commit()
        return new


@dataclass
class SyncAll:
    uow: UnitOfWork
    sync_connection: SyncConnection

    def __call__(self) -> int:
        with self.uow:
            ids = [c.id for c in self.uow.connections.active() if c.id is not None]
        return sum(self.sync_connection(connection_id).new for connection_id in ids)


@dataclass
class CompleteAuthorization:
    """Handles the bank's redirect: creates the connection, links its accounts and runs a first sync.

    Returns False (and changes nothing) when the bank reported an error, data is missing or the session fails.
    """

    uow: UnitOfWork
    provider: BankingProvider
    sync_connection: SyncConnection

    def __call__(self, code: str | None, state: str | None, error: str | None) -> bool:
        with self.uow:
            pending = self.uow.pending.get(state) if state else None
            if error or not code or pending is None:
                return False
            try:
                session = self.provider.create_session(code)
            except (ProviderError, ProviderNotConfigured) as e:
                log.warning("Error creando sesión: %s", e)
                return False

            connection = BankConnection(
                aspsp_name=pending.aspsp_name,
                aspsp_country=pending.aspsp_country,
                session_id=session["session_id"],
                valid_until=datetime.fromisoformat(session["access"]["valid_until"]),
            )
            self.uow.connections.save(connection)
            connection_id = saved_id(connection.id, "BankConnection")
            known = self.uow.accounts.all()
            for payload in session["accounts"]:
                account = link_account(IncomingAccount.from_session(payload), connection_id, pending.aspsp_name, known)
                self.uow.accounts.save(account)
                if account not in known:
                    known.append(account)
            self.uow.pending.delete(pending.state)
            self.uow.commit()
        try:
            self.sync_connection(connection_id)
        except Exception:
            log.exception("Falló la primera sincronización")
        return True


@dataclass
class UpdateAccount:
    uow: UnitOfWork
    events: EventPublisher

    def __call__(self, account_id: AccountId, role: AccountRole | None, alias: str | None, iban: str | None) -> Account:
        with self.uow:
            account = self.uow.accounts.by_id(account_id)
            if account is None:
                raise AccountNotFound()
            iban_changed = account.update(role, alias, iban)
            self.uow.accounts.save(account)
            self.uow.commit()
        if iban_changed:
            self.events.publish(AccountIbanChanged(account_id))
        return account


@dataclass
class OwnAccountIbans:
    uow: UnitOfWork

    def __call__(self) -> set[str]:
        with self.uow:
            return {a.iban.value for a in self.uow.accounts.all() if a.iban}


@dataclass
class AccountSnapshots:
    uow: UnitOfWork

    def __call__(self) -> list[AccountSnapshot]:
        with self.uow:
            return [
                AccountSnapshot(a.id, a.role, a.balance.amount if a.balance else None)
                for a in self.uow.accounts.all()
                if a.id is not None
            ]


@dataclass
class AccountDisplayNames:
    uow: UnitOfWork

    def __call__(self, account_ids: Collection[AccountId]) -> dict[AccountId, str]:
        with self.uow:
            return {a.id: a.display_name for a in self.uow.accounts.by_ids(account_ids) if a.id is not None}


@dataclass(frozen=True)
class BankingServices:
    """The banking use cases bound to one unit of work."""

    list_connections: ListConnections
    remove_connection: RemoveConnection
    list_available_banks: ListAvailableBanks
    start_authorization: StartAuthorization
    complete_authorization: CompleteAuthorization
    sync_connection: SyncConnection
    sync_all: SyncAll
    update_account: UpdateAccount
    own_account_ibans: OwnAccountIbans
    account_display_names: AccountDisplayNames
    account_snapshots: AccountSnapshots
