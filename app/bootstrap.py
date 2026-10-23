"""Composition root: builds the adapters, binds them to the use cases and plugs them into FastAPI and the CLI.

This is the only module outside a bounded context allowed to import the contexts' internals.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import FastAPI
from sqlalchemy.orm import Session

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


_current: Container | None = None


def wire(app: FastAPI, container: Container) -> None:
    """Points the app's dependencies at `container`; call again to swap it (e.g. one per test)."""
    global _current
    _current = container
    app.dependency_overrides[identity_services] = container.identity
    app.dependency_overrides[categorization_services] = container.categorization
    if not getattr(app.state, "context_routers_included", False):
        app.include_router(identity_router)
        app.include_router(categorization_router)
        app.state.context_routers_included = True


def current() -> Container:
    """Transitional service locator for legacy modules that are not yet bounded contexts; contexts never use it."""
    if _current is None:
        raise RuntimeError("No container wired: call app.bootstrap.wire(app, container) first")
    return _current


def create_user(username: str, container: Container | None = None) -> None:
    create_user_command(username, (container or Container.from_environment()).identity().create_user)
