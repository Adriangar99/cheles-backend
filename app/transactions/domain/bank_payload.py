"""Anti-corruption layer: turns an Enable Banking transaction payload (`raw`) into transaction fields.

Pure translation, so it can run both on ingestion and when reprocessing stored payloads.
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.shared.money import Money
from app.transactions.domain.counterparty import CounterpartyIban
from app.transactions.domain.errors import UndatedTransaction

DESCRIPTION_MAX_LENGTH = 1024
REMITTANCE_SEPARATOR = " // "
# Detail of a BBVA card payment: merchant (25), city (13) and country (2), each padded with spaces
CARD_DETAIL_LENGTH = 40
CARD_MERCHANT_LENGTH = 25


@dataclass(frozen=True)
class NormalizedTransaction:
    external_id: str
    booking_date: date
    amount: Money
    status: str
    counterparty: str | None
    counterparty_iban: CounterpartyIban | None
    description: str


def _external_id(raw: dict[str, Any], booking_date: date, amount: Decimal, description: str) -> str:
    if raw.get("entry_reference"):
        return f"ref:{raw['entry_reference']}"
    if raw.get("transaction_id"):
        return f"id:{raw['transaction_id']}"
    digest = hashlib.sha256(f"{booking_date}|{amount}|{description}".encode()).hexdigest()[:32]
    return f"h:{digest}"


def normalize(raw: dict[str, Any]) -> NormalizedTransaction:
    amount = Decimal(raw["transaction_amount"]["amount"])
    is_debit = raw.get("credit_debit_indicator") == "DBIT"
    if is_debit:
        amount = -abs(amount)
    party, party_account = ("creditor", "creditor_account") if is_debit else ("debtor", "debtor_account")
    description = " ".join(raw.get("remittance_information") or []).strip()
    if not description:
        description = ((raw.get("bank_transaction_code") or {}).get("description") or "").strip()
    raw_date = raw.get("booking_date") or raw.get("value_date") or raw.get("transaction_date")
    if not raw_date:
        raise UndatedTransaction()
    booking_date = date.fromisoformat(raw_date)
    return NormalizedTransaction(
        # The id hashes the full description, before truncation
        external_id=_external_id(raw, booking_date, amount, description),
        booking_date=booking_date,
        amount=Money(amount, raw["transaction_amount"].get("currency", "EUR")),
        status=raw.get("status", "BOOK"),
        counterparty=((raw.get(party) or {}).get("name") or None),
        counterparty_iban=CounterpartyIban.parse((raw.get(party_account) or {}).get("iban")),
        description=description[:DESCRIPTION_MAX_LENGTH],
    )


def remittance_title(description: str) -> str | None:
    """The readable part of a `sector // operation // detail` description: the merchant in the detail, or the operation
    when the detail is only a reference number. None when the description has another format."""
    segments = description.split(REMITTANCE_SEPARATOR)
    if len(segments) < 3:
        return None
    detail = segments[-1]
    merchant = (detail[:CARD_MERCHANT_LENGTH] if len(detail) == CARD_DETAIL_LENGTH else detail).strip()
    if any(c.isalpha() for c in merchant):
        return merchant
    return segments[-2].strip() or None
