"""Unit tests for re-linking known accounts when a bank is reconnected (pure domain)."""

from app.banking.domain.account import Account, Iban
from app.banking.domain.reconnection import IncomingAccount, link_account


def known(**fields: object) -> Account:
    defaults: dict[str, object] = {"name": "Cuenta", "currency": "EUR"}
    return Account(**{**defaults, **fields})  # type: ignore[arg-type]


def test_matches_by_identification_hash_first() -> None:
    by_iban = known(id=1, iban=Iban("ES111"))
    by_hash = known(id=2, identification_hash="h1", role="savings", alias="Hucha")

    account = link_account(
        IncomingAccount(uid="u-new", name="X", currency="EUR", identification_hash="h1", iban=Iban("ES111")),
        connection_id=7,
        bank_name="BBVA",
        known=[by_iban, by_hash],
    )

    assert account is by_hash
    assert (account.connection_id, account.eb_uid, account.role, account.alias) == (7, "u-new", "savings", "Hucha")


def test_falls_back_to_the_normalized_iban_and_takes_the_new_hash() -> None:
    existing = known(id=1, identification_hash="old", iban=Iban("ES123456"))

    account = link_account(
        IncomingAccount(uid="u2", name=None, currency=None, identification_hash="new", iban=Iban.parse("es12 3456")),
        connection_id=7,
        bank_name="BBVA",
        known=[existing],
    )

    assert account is existing
    assert account.identification_hash == "new"


def test_creates_a_new_account_when_nothing_matches() -> None:
    account = link_account(
        IncomingAccount(uid="u3", name=None, currency=None, identification_hash="h9", iban=None),
        connection_id=7,
        bank_name="BBVA",
        known=[known(id=1, identification_hash="h1")],
    )

    assert account.id is None
    assert (account.name, account.currency, account.role, account.eb_uid) == ("BBVA", "EUR", "main", "u3")


def test_an_incoming_account_without_iban_keeps_the_stored_one() -> None:
    existing = known(id=1, identification_hash="h1", iban=Iban("ES123456"))

    account = link_account(
        IncomingAccount(uid="u2", name="X", currency="EUR", identification_hash="h1", iban=None),
        connection_id=7,
        bank_name="BBVA",
        known=[existing],
    )

    assert account.iban == Iban("ES123456")
