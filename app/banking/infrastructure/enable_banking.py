"""Minimal Enable Banking API client (https://enablebanking.com/docs/api/reference/); banking's BankingProvider."""

import time
from datetime import date, datetime
from typing import Any

import httpx
import jwt

from app.banking.domain.errors import ProviderError
from app.config import get_settings


class EnableBankingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.eb_api_url
        self.application_id = settings.eb_application_id
        self.private_key_path = settings.eb_private_key_path
        self._token: str | None = None
        self._token_exp = 0

    def _jwt(self) -> str:
        # The JWT lasts at most 24 h; renew it with some margin
        now = int(time.time())
        if self._token and now < self._token_exp - 300:
            return self._token
        if not self.application_id:
            raise RuntimeError("EB_APPLICATION_ID is not configured")
        with open(self.private_key_path, "rb") as f:
            private_key = f.read()
        self._token_exp = now + 3600
        self._token = jwt.encode(
            {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": self._token_exp},
            private_key,
            algorithm="RS256",
            headers={"kid": self.application_id},
        )
        return self._token

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=60) as client:
            response = client.request(method, path, headers={"Authorization": f"Bearer {self._jwt()}"}, **kwargs)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise ProviderError(response.status_code, body)
        return response.json()

    def list_aspsps(self, country: str) -> list[dict[str, Any]]:
        aspsps: list[dict[str, Any]] = self._request(
            "GET", "/aspsps", params={"country": country, "psu_type": "personal"}
        )["aspsps"]
        return aspsps

    def start_auth(self, aspsp_name: str, country: str, state: str, redirect_url: str, valid_until: datetime) -> str:
        data = self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until.isoformat()},
                "aspsp": {"name": aspsp_name, "country": country},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": "personal",
                "language": "es",
            },
        )
        url: str = data["url"]
        return url

    def create_session(self, code: str) -> dict[str, Any]:
        session: dict[str, Any] = self._request("POST", "/sessions", json={"code": code})
        return session

    def delete_session(self, session_id: str) -> None:
        self._request("DELETE", f"/sessions/{session_id}")

    def get_balances(self, account_uid: str) -> list[dict[str, Any]]:
        balances: list[dict[str, Any]] = self._request("GET", f"/accounts/{account_uid}/balances")["balances"]
        return balances

    def get_transactions(self, account_uid: str, date_from: date) -> list[dict[str, Any]]:
        params: dict[str, str] = {"date_from": date_from.isoformat()}
        transactions: list[dict[str, Any]] = []
        while True:
            data = self._request("GET", f"/accounts/{account_uid}/transactions", params=params)
            transactions.extend(data.get("transactions", []))
            continuation_key = data.get("continuation_key")
            if not continuation_key:
                return transactions
            params["continuation_key"] = continuation_key
