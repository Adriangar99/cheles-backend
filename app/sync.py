"""Banking sync (legacy): reads accounts from Enable Banking and hands their transactions to transactions."""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.enablebanking import EnableBankingClient, EnableBankingError
from app.models import Account, BankConnection
from app.shared.ids import AccountId
from app.transactions.public import TransactionsServices

log = logging.getLogger(__name__)

BALANCE_PREFERENCE = ["ITAV", "CLAV", "XPCD", "ITBD", "CLBD"]
# Re-read this many days before the latest booked transaction, to catch late bookings
OVERLAP_DAYS = 10


def normalize_iban(iban: str | None) -> str | None:
    return iban.replace(" ", "").upper() if iban else None


def _pick_balance(balances: list[dict[str, Any]]) -> Decimal | None:
    by_type = {b.get("balance_type"): b for b in balances}
    for balance_type in BALANCE_PREFERENCE:
        if balance_type in by_type:
            return Decimal(by_type[balance_type]["balance_amount"]["amount"])
    return Decimal(balances[0]["balance_amount"]["amount"]) if balances else None


def sync_account(db: Session, client: EnableBankingClient, account: Account, transactions: TransactionsServices) -> int:
    uid = account.eb_uid
    assert uid is not None, "sync_connection only syncs accounts linked to Enable Banking"
    account_id = AccountId(account.id)
    last_date = transactions.latest_booked_date(account_id)
    if last_date:
        date_from = last_date - timedelta(days=OVERLAP_DAYS)
    else:
        date_from = date.today() - timedelta(days=get_settings().initial_history_days)

    # Both Enable Banking calls happen before writing, so a failure stores nothing for this account
    raws = client.get_transactions(uid, date_from)
    balances = client.get_balances(uid)

    new_count = transactions.ingest(account_id, raws)
    account.balance = _pick_balance(balances)
    account.balance_at = datetime.now(UTC)
    db.commit()
    return new_count


def sync_connection(
    db: Session,
    connection: BankConnection,
    transactions: TransactionsServices,
    client: EnableBankingClient | None = None,
) -> int:
    client = client or EnableBankingClient()
    if connection.valid_until < datetime.now(UTC):
        connection.status = "expired"
        db.commit()
        return 0
    total = 0
    try:
        for account in connection.accounts:
            if account.eb_uid:
                total += sync_account(db, client, account, transactions)
        connection.last_error = None
    except EnableBankingError as e:
        db.rollback()
        log.warning("Error sincronizando %s: %s", connection.aspsp_name, e)
        connection.last_error = str(e)[:1024]
        if e.status_code in (401, 403):
            connection.status = "expired"
    connection.last_synced_at = datetime.now(UTC)
    db.commit()
    return total


def sync_all(db: Session, transactions: TransactionsServices) -> int:
    client = EnableBankingClient()
    connections = db.scalars(select(BankConnection).where(BankConnection.status == "active")).all()
    return sum(sync_connection(db, c, transactions, client) for c in connections)
