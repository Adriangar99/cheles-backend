from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PendingAuth(Base):
    """Autorización con un banco en curso (entre POST /auth y el callback)."""

    __tablename__ = "pending_auths"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    aspsp_name: Mapped[str] = mapped_column(String(128))
    aspsp_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankConnection(Base):
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

    accounts: Mapped[list["Account"]] = relationship(back_populates="connection")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("bank_connections.id", ondelete="SET NULL"))
    # uid de Enable Banking (cambia en cada reconexión) y hash estable de la cuenta
    eb_uid: Mapped[str | None] = mapped_column(String(128))
    identification_hash: Mapped[str | None] = mapped_column(String(256), unique=True)
    iban: Mapped[str | None] = mapped_column(String(34))
    name: Mapped[str] = mapped_column(String(128))
    alias: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # main: día a día (nómina y pagos) | savings: ahorro | excluded: no cuenta en estadísticas
    role: Mapped[str] = mapped_column(String(16), default="main")
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    balance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connection: Mapped[BankConnection | None] = relationship(back_populates="accounts")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("account_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(256))
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # negativo = sale dinero
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(8))  # BOOK | PDNG
    counterparty: Mapped[str | None] = mapped_column(String(256))
    counterparty_iban: Mapped[str | None] = mapped_column(String(34))
    description: Mapped[str] = mapped_column(String(1024), default="")
    # transfer: entre cuentas propias (no es gasto ni ingreso)
    kind: Mapped[str] = mapped_column(String(16), default="normal")  # normal | transfer
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(512))
    # Respuesta original del banco: permite reprocesar sin volver a pedir datos
    raw: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship()
