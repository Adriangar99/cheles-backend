"""In-memory stand-in for the Enable Banking API, with the same public methods as `EnableBankingClient`."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.enablebanking import EnableBankingError


@dataclass
class FakeAccount:
    uid: str
    name: str | None = None
    iban: str | None = None
    identification_hash: str | None = None
    currency: str | None = "EUR"

    def as_session_account(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "currency": self.currency,
            "identification_hash": self.identification_hash,
            "account_id": {"iban": self.iban} if self.iban else None,
        }


@dataclass
class FakeEnableBanking:
    aspsps: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"name": "BBVA", "country": "ES", "logo": "https://logos.example/bbva.png"},
            {"name": "Revolut", "country": "ES", "logo": "https://logos.example/revolut.png"},
        ]
    )
    # Authorization code -> session returned by create_session
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    transactions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    balances: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    # Method name (optionally "method:uid") -> error raised on the next call(s)
    _errors: dict[str, Exception] = field(default_factory=dict)

    # ---- test setup helpers ----

    def fail(
        self,
        method: str,
        status_code: int = 500,
        body: Any = "boom",
        uid: str | None = None,
        error: Exception | None = None,
    ) -> None:
        """Makes every later call to `method` (for one account uid, if given) raise an Enable Banking error."""
        self._errors[f"{method}:{uid}" if uid else method] = error or EnableBankingError(status_code, body)

    def recover(self) -> None:
        self._errors.clear()

    def add_session(
        self, code: str, accounts: list[FakeAccount], valid_until: str = "2027-04-01T00:00:00+00:00"
    ) -> str:
        session_id = f"session-{code}"
        self.sessions[code] = {
            "session_id": session_id,
            "access": {"valid_until": valid_until},
            "accounts": [a.as_session_account() for a in accounts],
        }
        return session_id

    def calls_to(self, method: str) -> list[tuple[Any, ...]]:
        return [args for name, args in self.calls if name == method]

    def _record(self, method: str, *args: Any, uid: str | None = None) -> None:
        self.calls.append((method, args))
        for key in (f"{method}:{uid}" if uid else None, method):
            if key and key in self._errors:
                raise self._errors[key]

    # ---- EnableBankingClient interface ----

    def list_aspsps(self, country: str) -> list[dict[str, Any]]:
        self._record("list_aspsps", country)
        return [a for a in self.aspsps if a["country"] == country]

    def start_auth(self, aspsp_name: str, country: str, state: str, redirect_url: str, valid_until: datetime) -> str:
        self._record("start_auth", aspsp_name, country, state, redirect_url, valid_until)
        return f"https://bank.example/{aspsp_name}/authorize?state={state}"

    def create_session(self, code: str) -> dict[str, Any]:
        self._record("create_session", code)
        if code not in self.sessions:
            raise EnableBankingError(422, {"message": "invalid code"})
        return self.sessions[code]

    def delete_session(self, session_id: str) -> None:
        self._record("delete_session", session_id)

    def get_balances(self, account_uid: str) -> list[dict[str, Any]]:
        self._record("get_balances", account_uid, uid=account_uid)
        return self.balances.get(account_uid, [])

    def get_transactions(self, account_uid: str, date_from: date) -> list[dict[str, Any]]:
        self._record("get_transactions", account_uid, date_from, uid=account_uid)
        # Like the real API, only transactions on or after date_from (pagination is the real client's job)
        return [t for t in self.transactions.get(account_uid, []) if _raw_date(t) >= date_from]


def _raw_date(raw: dict[str, Any]) -> date:
    value = raw.get("booking_date") or raw.get("value_date") or raw.get("transaction_date")
    return date.fromisoformat(str(value))
