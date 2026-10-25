"""Matching a received transaction with a pending one the bank replaced, so the user's edits carry over."""

from app.transactions.domain.transaction import Transaction

MAX_DAYS_APART = 3


def _same_party(a: Transaction, b: Transaction) -> bool:
    if a.counterparty or b.counterparty:
        return (a.counterparty or "").casefold() == (b.counterparty or "").casefold()
    return a.description.casefold() == b.description.casefold()


def matching_pending(incoming: Transaction, pendings: list[Transaction]) -> Transaction | None:
    """The pending transaction `incoming` replaces: the same external id or else the same amount and counterparty (or
    description) at most 3 days apart, the closest date first. `pendings` belong to the same account."""
    for pending in pendings:
        if pending.external_id == incoming.external_id:
            return pending
    candidates = [
        p
        for p in pendings
        if p.amount == incoming.amount
        and _same_party(p, incoming)
        and abs((p.booking_date - incoming.booking_date).days) <= MAX_DAYS_APART
    ]
    return min(candidates, key=lambda p: (abs((p.booking_date - incoming.booking_date).days), p.id or 0), default=None)
