"""Persistence row for transactions; table unchanged from before the migration to bounded contexts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TransactionRow(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("account_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(256))
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # negative: money going out
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(8))  # BOOK | PDNG
    counterparty: Mapped[str | None] = mapped_column(String(256))
    counterparty_iban: Mapped[str | None] = mapped_column(String(34))
    description: Mapped[str] = mapped_column(String(1024), default="")
    source: Mapped[str] = mapped_column(String(8), default="bank", server_default="bank")  # bank | import
    kind: Mapped[str] = mapped_column(String(16), default="normal")  # normal | transfer (between own accounts)
    kind_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(512))
    # The bank's original payload, so transactions can be reprocessed without fetching them again
    raw: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
