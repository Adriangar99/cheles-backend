"""Composition root: builds the adapters, binds them to the use cases and plugs them into FastAPI and the CLI.

This is the only module outside a bounded context allowed to import the contexts' internals.
"""

import secrets
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.banking.application.ports import BankingProvider, BankingSettings
from app.banking.application.use_cases import (
    AccountDisplayNames,
    AccountSnapshots,
    BankingServices,
    CompleteAuthorization,
    ListAvailableBanks,
    ListConnections,
    OwnAccountIbans,
    RemoveConnection,
    StartAuthorization,
    SyncAll,
    SyncConnection,
    UpdateAccount,
)
from app.banking.domain.events import AccountIbanChanged
from app.banking.infrastructure.clock import SystemClock as BankingClock
from app.banking.infrastructure.enable_banking import EnableBankingClient
from app.banking.infrastructure.http import banking_services
from app.banking.infrastructure.http import router as banking_router
from app.banking.infrastructure.repositories import SqlUnitOfWork as BankingUnitOfWork
from app.categorization.application.use_cases import (
    CategorizationServices,
    CategoryExists,
    CategoryLabels,
    CreateRule,
    ListCategories,
    LoadPolicy,
    SeedDefaultCatalog,
)
from app.categorization.infrastructure.http import categorization_services
from app.categorization.infrastructure.http import router as categorization_router
from app.categorization.infrastructure.repositories import SqlUnitOfWork as CategorizationUnitOfWork
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.identity.application.ports import Clock, PasswordHasher, TokenGenerator, TotpService
from app.identity.application.use_cases import Authenticate, CreateUser, IdentityServices, LogIn, LogOut
from app.identity.domain.throttle import LoginThrottle
from app.identity.infrastructure.cli import create_user_command
from app.identity.infrastructure.http import identity_services
from app.identity.infrastructure.http import router as identity_router
from app.identity.infrastructure.repositories import SqlUnitOfWork as IdentityUnitOfWork
from app.identity.infrastructure.security import (
    Argon2PasswordHasher,
    PyotpTotpService,
    SecretsTokenGenerator,
    SystemClock,
)
from app.shared.events import InMemoryEventBus
from app.shared.ids import AccountId, CategoryId
from app.stats.application.use_cases import MonthlyHistory, MonthlySummary, StatsServices
from app.stats.domain.figures import AccountStanding, Movement, SpendingLabel
from app.stats.infrastructure.clock import SystemClock as StatsClock
from app.stats.infrastructure.http import router as stats_router
from app.stats.infrastructure.http import stats_services
from app.transactions.application.use_cases import (
    EditTransaction,
    Ingest,
    LatestBookedDate,
    ListMovements,
    ListTransactions,
    ReprocessAll,
    TransactionsServices,
)
from app.transactions.domain.transaction import CategorySuggester
from app.transactions.infrastructure.http import router as transactions_router
from app.transactions.infrastructure.http import transactions_services
from app.transactions.infrastructure.repositories import SqlUnitOfWork as TransactionsUnitOfWork


@dataclass
class Container:
    """Long-lived adapters and state shared by every request (e.g. the in-memory login throttle)."""

    settings: Settings
    session_factory: Callable[[], Session]
    hasher: PasswordHasher = field(default_factory=Argon2PasswordHasher)
    totp: TotpService = field(default_factory=PyotpTotpService)
    clock: Clock = field(default_factory=SystemClock)
    tokens: TokenGenerator = field(default_factory=SecretsTokenGenerator)
    login_throttle: LoginThrottle = field(default_factory=LoginThrottle)
    banking_provider: BankingProvider = field(default_factory=EnableBankingClient)
    events: InMemoryEventBus = field(default_factory=InMemoryEventBus)

    def __post_init__(self) -> None:
        # A new or removed own IBAN changes which movements are transfers between own accounts
        self.events.subscribe(AccountIbanChanged, self._reprocess_transactions)

    def _reprocess_transactions(self, _: AccountIbanChanged) -> None:
        self.transactions().reprocess_all()

    @classmethod
    def from_environment(cls) -> "Container":
        return cls(settings=get_settings(), session_factory=SessionLocal)

    def identity(self) -> IdentityServices:
        uow = IdentityUnitOfWork(self.session_factory)
        return IdentityServices(
            log_in=LogIn(
                uow=uow,
                hasher=self.hasher,
                totp=self.totp,
                clock=self.clock,
                tokens=self.tokens,
                throttle=self.login_throttle,
                session_days=self.settings.session_days,
            ),
            log_out=LogOut(uow=uow),
            authenticate=Authenticate(uow=uow, clock=self.clock),
            create_user=CreateUser(uow=uow, hasher=self.hasher, totp=self.totp),
        )

    def categorization(self) -> CategorizationServices:
        uow = CategorizationUnitOfWork(self.session_factory)
        return CategorizationServices(
            seed_default_catalog=SeedDefaultCatalog(uow=uow),
            list_categories=ListCategories(uow=uow),
            create_rule=CreateRule(uow=uow),
            category_exists=CategoryExists(uow=uow),
            load_policy=LoadPolicy(uow=uow),
            category_labels=CategoryLabels(uow=uow),
        )

    def transactions(self) -> TransactionsServices:
        uow = TransactionsUnitOfWork(self.session_factory)
        own_accounts = _BankingOwnAccounts(self)
        suggestions = _CategorizationSuggestions(self)
        reprocess_all = ReprocessAll(uow=uow, own_accounts=own_accounts, suggestions=suggestions)
        return TransactionsServices(
            ingest=Ingest(uow=uow, own_accounts=own_accounts, suggestions=suggestions),
            latest_booked_date=LatestBookedDate(uow=uow),
            list_movements=ListMovements(uow=uow),
            reprocess_all=reprocess_all,
            list_transactions=ListTransactions(uow=uow, own_accounts=own_accounts),
            edit_transaction=EditTransaction(
                uow=uow,
                own_accounts=own_accounts,
                catalog=_CategorizationCatalog(self),
                suggestions=suggestions,
                reprocess_all=reprocess_all,
            ),
        )

    def banking(self) -> BankingServices:
        uow = BankingUnitOfWork(self.session_factory)
        settings = BankingSettings(
            country=self.settings.eb_country,
            consent_days=self.settings.eb_consent_days,
            redirect_url=self.settings.eb_redirect_url,
            initial_history_days=self.settings.initial_history_days,
        )
        clock = BankingClock()
        sync_connection = SyncConnection(
            uow=uow,
            provider=self.banking_provider,
            transactions=_TransactionsGateway(self),
            settings=settings,
            clock=clock,
        )
        return BankingServices(
            list_connections=ListConnections(uow=uow),
            remove_connection=RemoveConnection(uow=uow, provider=self.banking_provider),
            list_available_banks=ListAvailableBanks(provider=self.banking_provider, settings=settings),
            start_authorization=StartAuthorization(
                uow=uow, provider=self.banking_provider, settings=settings, clock=clock, states=_UrlSafeStates()
            ),
            complete_authorization=CompleteAuthorization(
                uow=uow, provider=self.banking_provider, sync_connection=sync_connection
            ),
            sync_connection=sync_connection,
            sync_all=SyncAll(uow=uow, sync_connection=sync_connection),
            update_account=UpdateAccount(uow=uow, events=self.events),
            own_account_ibans=OwnAccountIbans(uow=uow),
            account_display_names=AccountDisplayNames(uow=uow),
            account_snapshots=AccountSnapshots(uow=uow),
        )

    def stats(self) -> StatsServices:
        movements, accounts = _TransactionsMovements(self), _BankingStandings(self)
        return StatsServices(
            monthly_summary=MonthlySummary(
                movements=movements, accounts=accounts, labels=_CategorizationLabels(self), clock=StatsClock()
            ),
            monthly_history=MonthlyHistory(movements=movements, accounts=accounts),
        )


class _TransactionsMovements:
    """Stats' `MovementsSource`, served by transactions' published movement records."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def between(self, start: date | None, end: date | None) -> list[Movement]:
        return [
            Movement(r.account_id, r.booking_date, r.amount, r.kind, r.category_id)
            for r in self.container.transactions().list_movements(start, end)
        ]


class _BankingStandings:
    """Stats' `AccountsSource`: banking's account snapshots translated into what stats cares about."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def standings(self) -> list[AccountStanding]:
        return [
            AccountStanding(
                account_id=s.account_id,
                counts=s.role != "excluded",
                is_savings=s.role == "savings",
                balance_group=s.role,
                balance=s.balance,
            )
            for s in self.container.banking().account_snapshots()
        ]


class _CategorizationLabels:
    """Stats' `CategoryLabelsSource`, served by categorization."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def labels(self, category_ids: Collection[CategoryId]) -> dict[CategoryId, SpendingLabel]:
        return {
            category_id: SpendingLabel(label.name, label.icon, label.color)
            for category_id, label in self.container.categorization().category_labels(category_ids).items()
        }


class _UrlSafeStates:
    def new_state(self) -> str:
        return secrets.token_urlsafe(24)


class _BankingOwnAccounts:
    """Transactions' `OwnAccounts` port, served by banking."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def ibans(self) -> set[str]:
        return self.container.banking().own_account_ibans()

    def display_names(self, account_ids: Collection[AccountId]) -> dict[AccountId, str]:
        return self.container.banking().account_display_names(account_ids)


class _TransactionsGateway:
    """Banking's `TransactionsGateway` port, served by transactions."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def latest_booked_date(self, account_id: AccountId) -> date | None:
        return self.container.transactions().latest_booked_date(account_id)

    def ingest(self, account_id: AccountId, raws: list[dict[str, Any]]) -> int:
        return self.container.transactions().ingest(account_id, raws)


class _CategorizationSuggestions:
    """Transactions' `CategorySuggestions` port, served by categorization."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def load(self) -> CategorySuggester:
        return self.container.categorization().load_policy()


class _CategorizationCatalog:
    """Transactions' `CategoryCatalog` port, served by categorization."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def exists(self, category_id: CategoryId) -> bool:
        return self.container.categorization().category_exists(category_id)


def wire(app: FastAPI, container: Container) -> None:
    """Points the app's dependencies at `container` and keeps it in `app.state.container` for the composition edge
    (startup and scheduled jobs in app.main); call again to swap it (e.g. one per test)."""
    app.state.container = container
    app.dependency_overrides[identity_services] = container.identity
    app.dependency_overrides[categorization_services] = container.categorization
    app.dependency_overrides[transactions_services] = container.transactions
    app.dependency_overrides[banking_services] = container.banking
    app.dependency_overrides[stats_services] = container.stats
    if not getattr(app.state, "context_routers_included", False):
        for router in (identity_router, categorization_router, transactions_router, banking_router, stats_router):
            app.include_router(router)
        app.state.context_routers_included = True


def create_user(username: str, container: Container | None = None) -> None:
    create_user_command(username, (container or Container.from_environment()).identity().create_user)
