"""Persistence rows for banking; tables unchanged from before the migration to bounded contexts."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PendingAuthRow(Base):
    """An authorization with a bank in progress (between /connect and the callback)."""

    __tablename__ = "pending_auths"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    aspsp_name: Mapped[str] = mapped_column(String(128))
    aspsp_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankConnectionRow(Base):
    __tablename__ = "bank_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    aspsp_name: Mapped[str] = mapped_column(String(128))
    aspsp_country: Mapped[str] = mapped_column(String(2))
    session_id: Mapped[str] = mapped_column(String(128), unique=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | expired | revoked
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    accounts: Mapped[list["AccountRow"]] = relationship(back_populates="connection")


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("bank_connections.id", ondelete="SET NULL"))
    # Enable Banking's uid (changes on every reconnection) and the account's stable hash
    eb_uid: Mapped[str | None] = mapped_column(String(128))
    identification_hash: Mapped[str | None] = mapped_column(String(256), unique=True)
    iban: Mapped[str | None] = mapped_column(String(34))
    name: Mapped[str] = mapped_column(String(128))
    alias: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # main: day to day (salary and payments) | savings | excluded: not counted in stats
    role: Mapped[str] = mapped_column(String(16), default="main")
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    balance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connection: Mapped[BankConnectionRow | None] = relationship(back_populates="accounts")
