"""Characterization of `banking/accounts`."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.infrastructure.orm import AccountRow as Account
from app.transactions.infrastructure.orm import TransactionRow as Transaction
from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx, stored_row

SAVINGS_IBAN = "ES9121000418450200051332"


@pytest.fixture
def user(client: TestClient, db: Session) -> None:
    login(client, db)


@pytest.fixture
def account_id(user: None, client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> int:
    connect_bank(client, fake_bank, [FakeAccount(uid="u1", name="Cuenta Online")])
    account_id: int = db.scalars(select(Account.id)).one()
    return account_id


def transfer_to_savings_account(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> Transaction:
    """A main account with a debit whose counterparty IBAN is a second account with no known IBAN yet."""
    fake_bank.transactions["main"] = [raw_tx("300.00", reference="t1", creditor_iban=SAVINGS_IBAN)]
    connect_bank(client, fake_bank, [FakeAccount(uid="main"), FakeAccount(uid="savings")])
    return db.scalars(select(Transaction)).one()


# ---------- List of connections and accounts ----------


@pytest.mark.usefixtures("user")
def test_connections_with_accounts(client: TestClient, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Connections with accounts"""
    first = connect_bank(client, fake_bank, [FakeAccount(uid="a1")], bank="BBVA", code="c1")
    second = connect_bank(client, fake_bank, [FakeAccount(uid="b1"), FakeAccount(uid="b2")], bank="Revolut", code="c2")

    body = client.get("/api/banks").json()

    assert [(c["id"], c["bank"], len(c["accounts"])) for c in body["connections"]] == [
        (first, "BBVA", 1),
        (second, "Revolut", 2),
    ]
    assert set(body["connections"][0]) == {
        "id",
        "bank",
        "status",
        "valid_until",
        "last_synced_at",
        "last_error",
        "accounts",
    }


@pytest.mark.usefixtures("user")
def test_accounts_without_a_connection(client: TestClient, db: Session) -> None:
    """Scenario: Accounts without a connection"""
    db.add(Account(name="Antigua", currency="EUR", role="main"))
    db.commit()

    body = client.get("/api/banks").json()

    assert body["connections"] == []
    assert [a["name"] for a in body["detached_accounts"]] == ["Antigua"]


# ---------- Account representation ----------


def test_account_with_an_alias(client: TestClient, account_id: int) -> None:
    """Scenario: Account with an alias"""
    client.patch(f"/api/accounts/{account_id}", json={"alias": "Nómina"})

    account = client.get("/api/banks").json()["connections"][0]["accounts"][0]

    assert account["name"] == "Nómina"
    assert set(account) == {"id", "name", "iban_tail", "currency", "role", "balance", "balance_at", "connection_id"}


def test_hidden_iban(client: TestClient, account_id: int) -> None:
    """Scenario: Hidden IBAN"""
    client.patch(f"/api/accounts/{account_id}", json={"iban": SAVINGS_IBAN})

    response = client.get("/api/banks")

    assert response.json()["connections"][0]["accounts"][0]["iban_tail"] == "1332"
    assert SAVINGS_IBAN not in response.text


# ---------- Account role ----------


def test_change_the_role(client: TestClient, account_id: int) -> None:
    """Scenario: Change the role"""
    response = client.patch(f"/api/accounts/{account_id}", json={"role": "savings"})

    assert response.status_code == 200
    assert response.json()["role"] == "savings"
    assert response.json()["id"] == account_id


def test_invalid_role(client: TestClient, db: Session, account_id: int) -> None:
    """Scenario: Invalid role"""
    response = client.patch(f"/api/accounts/{account_id}", json={"role": "investment"})

    assert response.status_code == 422
    assert stored_row(db, Account, account_id).role == "main"


@pytest.mark.usefixtures("user")
def test_unknown_account(client: TestClient) -> None:
    """Scenario: Unknown account"""
    assert client.patch("/api/accounts/999", json={"role": "savings"}).status_code == 404


# ---------- Account alias ----------


def test_set_an_alias(client: TestClient, account_id: int) -> None:
    """Scenario: Set an alias"""
    response = client.patch(f"/api/accounts/{account_id}", json={"alias": "Nómina"})

    assert response.json()["name"] == "Nómina"


def test_remove_the_alias(client: TestClient, account_id: int) -> None:
    """Scenario: Remove the alias"""
    client.patch(f"/api/accounts/{account_id}", json={"alias": "Nómina"})

    response = client.patch(f"/api/accounts/{account_id}", json={"alias": ""})

    assert response.json()["name"] == "Cuenta Online"


# ---------- Manual account IBAN ----------


@pytest.mark.usefixtures("user")
def test_set_the_iban(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Set the IBAN"""
    transaction = transfer_to_savings_account(client, db, fake_bank)
    assert transaction.kind == "normal"
    savings = db.scalars(select(Account).where(Account.eb_uid == "savings")).one()

    client.patch(f"/api/accounts/{savings.id}", json={"iban": "es91 2100 0418 4502 0005 1332"})
    assert stored_row(db, Account, savings.id).iban == SAVINGS_IBAN
    assert stored_row(db, Transaction, transaction.id).kind == "transfer"


@pytest.mark.usefixtures("user")
def test_remove_the_iban(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Remove the IBAN"""
    transaction = transfer_to_savings_account(client, db, fake_bank)
    savings = db.scalars(select(Account).where(Account.eb_uid == "savings")).one()
    client.patch(f"/api/accounts/{savings.id}", json={"iban": SAVINGS_IBAN})
    assert stored_row(db, Transaction, transaction.id).kind == "transfer"

    client.patch(f"/api/accounts/{savings.id}", json={"iban": ""})
    assert stored_row(db, Account, savings.id).iban is None
    assert stored_row(db, Transaction, transaction.id).kind == "normal"


@pytest.mark.usefixtures("user")
def test_changes_without_an_iban(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    """Scenario: Changes without an IBAN"""
    transaction = transfer_to_savings_account(client, db, fake_bank)
    savings = db.scalars(select(Account).where(Account.eb_uid == "savings")).one()
    savings.iban = SAVINGS_IBAN  # known IBAN, but stored without going through the API (no reprocess yet)
    db.commit()

    client.patch(f"/api/accounts/{savings.id}", json={"role": "savings", "alias": "Hucha"})
    assert stored_row(db, Transaction, transaction.id).kind == "normal"
