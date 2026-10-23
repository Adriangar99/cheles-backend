"""Transitional: legacy code still uses these names until it moves to the banking context (removed in this change)."""

from app.banking.infrastructure.orm import AccountRow, BankConnectionRow, PendingAuthRow

Account = AccountRow
BankConnection = BankConnectionRow
PendingAuth = PendingAuthRow
