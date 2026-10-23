import hashlib
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.categorize import Categorizer
from app.config import get_settings
from app.enablebanking import EnableBankingClient, EnableBankingError
from app.models import Account, BankConnection, Transaction

log = logging.getLogger(__name__)

BALANCE_PREFERENCE = ["ITAV", "CLAV", "XPCD", "ITBD", "CLBD"]


def normalize_iban(iban: str | None) -> str | None:
    return iban.replace(" ", "").upper() if iban else None


def _iban_of(party_account: dict[str, Any] | None) -> str | None:
    return normalize_iban((party_account or {}).get("iban"))


def _external_id(raw: dict[str, Any], booking_date: date, amount: Decimal, description: str) -> str:
    if raw.get("entry_reference"):
        return f"ref:{raw['entry_reference']}"
    if raw.get("transaction_id"):
        return f"id:{raw['transaction_id']}"
    digest = hashlib.sha256(f"{booking_date}|{amount}|{description}".encode()).hexdigest()[:32]
    return f"h:{digest}"


def normalize_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    amount = Decimal(raw["transaction_amount"]["amount"])
    is_debit = raw.get("credit_debit_indicator") == "DBIT"
    if is_debit:
        amount = -abs(amount)
    party, party_account = ("creditor", "creditor_account") if is_debit else ("debtor", "debtor_account")
    description = " ".join(raw.get("remittance_information") or []).strip()
    if not description:
        description = ((raw.get("bank_transaction_code") or {}).get("description") or "").strip()
    booking_date = date.fromisoformat(
        cast(str, raw.get("booking_date") or raw.get("value_date") or raw.get("transaction_date"))
    )
    return {
        "external_id": _external_id(raw, booking_date, amount, description),
        "booking_date": booking_date,
        "amount": amount,
        "currency": raw["transaction_amount"].get("currency", "EUR"),
        "status": raw.get("status", "BOOK"),
        "counterparty": ((raw.get(party) or {}).get("name") or None),
        "counterparty_iban": _iban_of(raw.get(party_account)),
        "description": description[:1024],
        "raw": raw,
    }


def own_ibans(db: Session) -> set[str]:
    return {iban for iban in db.scalars(select(Account.iban)) if iban}


def apply_derived_fields(tx: Transaction, ibans: set[str], categorizer: Categorizer) -> None:
    """Campos calculados a partir de los datos del banco. No toca lo editado a mano."""
    tx.kind = "transfer" if tx.counterparty_iban and tx.counterparty_iban in ibans else "normal"
    if not tx.category_manual:
        tx.category_id = None if tx.kind == "transfer" else categorizer.categorize(tx)


def _pick_balance(balances: list[dict[str, Any]]) -> Decimal | None:
    by_type = {b.get("balance_type"): b for b in balances}
    for balance_type in BALANCE_PREFERENCE:
        if balance_type in by_type:
            return Decimal(by_type[balance_type]["balance_amount"]["amount"])
    return Decimal(balances[0]["balance_amount"]["amount"]) if balances else None


def sync_account(db: Session, client: EnableBankingClient, account: Account) -> int:
    uid = account.eb_uid
    assert uid is not None, "sync_connection only syncs accounts linked to Enable Banking"
    last_date = db.scalar(
        select(func.max(Transaction.booking_date)).where(
            Transaction.account_id == account.id, Transaction.status == "BOOK"
        )
    )
    if last_date:
        date_from = last_date - timedelta(days=10)
    else:
        date_from = date.today() - timedelta(days=get_settings().initial_history_days)

    raws = client.get_transactions(uid, date_from)

    # Los pendientes cambian de id al confirmarse: los borramos y vuelven a llegar
    db.execute(delete(Transaction).where(Transaction.account_id == account.id, Transaction.status == "PDNG"))

    ibans = own_ibans(db)
    categorizer = Categorizer(db)
    new_count = 0
    for raw in raws:
        data = normalize_transaction(raw)
        tx = db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id, Transaction.external_id == data["external_id"]
            )
        )
        if tx is None:
            tx = Transaction(account_id=account.id, category_manual=False, **data)
            db.add(tx)
            new_count += 1
        else:
            for key, value in data.items():
                setattr(tx, key, value)
        apply_derived_fields(tx, ibans, categorizer)

    account.balance = _pick_balance(client.get_balances(uid))
    account.balance_at = datetime.now(UTC)
    db.commit()
    return new_count


def sync_connection(db: Session, connection: BankConnection, client: EnableBankingClient | None = None) -> int:
    client = client or EnableBankingClient()
    if connection.valid_until < datetime.now(UTC):
        connection.status = "expired"
        db.commit()
        return 0
    total = 0
    try:
        for account in connection.accounts:
            if account.eb_uid:
                total += sync_account(db, client, account)
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


def sync_all(db: Session) -> int:
    client = EnableBankingClient()
    connections = db.scalars(select(BankConnection).where(BankConnection.status == "active")).all()
    return sum(sync_connection(db, c, client) for c in connections)


def reprocess_all(db: Session) -> int:
    """Recalcula transferencias y categorías desde los datos crudos guardados."""
    ibans = own_ibans(db)
    categorizer = Categorizer(db)
    transactions = db.scalars(select(Transaction)).all()
    for tx in transactions:
        for key, value in normalize_transaction(tx.raw).items():
            if key != "external_id":
                setattr(tx, key, value)
        apply_derived_fields(tx, ibans, categorizer)
    db.commit()
    return len(transactions)
