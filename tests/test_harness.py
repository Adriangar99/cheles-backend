"""Checks the test harness itself, so characterization failures are never caused by the helpers."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fakes import FakeAccount, FakeEnableBanking
from tests.helpers import connect_bank, login, raw_tx


def test_connects_a_fake_bank_end_to_end(client: TestClient, db: Session, fake_bank: FakeEnableBanking) -> None:
    login(client, db)
    fake_bank.transactions["uid-1"] = [raw_tx("12.50", reference="r1", creditor="MERCADONA")]

    connection_id = connect_bank(client, fake_bank, [FakeAccount(uid="uid-1", name="Cuenta Online")])

    banks = client.get("/api/banks").json()
    assert [c["id"] for c in banks["connections"]] == [connection_id]
    assert banks["connections"][0]["accounts"][0]["name"] == "Cuenta Online"
    transactions = client.get("/api/transactions").json()
    assert [(t["counterparty"], t["amount"]) for t in transactions] == [("MERCADONA", -12.5)]


def test_client_ip_header_sets_the_client_address(client: TestClient) -> None:
    for _ in range(5):
        client.post(
            "/api/auth/login",
            json={"username": "x", "password": "y", "code": "000000"},
            headers={"X-Test-Client-IP": "10.0.0.1"},
        )

    blocked = client.post(
        "/api/auth/login",
        json={"username": "x", "password": "y", "code": "0"},
        headers={"X-Test-Client-IP": "10.0.0.1"},
    )
    other_ip = client.post(
        "/api/auth/login",
        json={"username": "x", "password": "y", "code": "0"},
        headers={"X-Test-Client-IP": "10.0.0.2"},
    )

    assert blocked.status_code == 429
    assert other_ip.status_code == 401
