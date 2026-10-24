from typing import Any


class ProviderError(Exception):
    """The bank data provider (Enable Banking) answered with an error."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Enable Banking {status_code}: {body}")


class ConnectionNotFound(Exception):
    pass


class AccountNotFound(Exception):
    pass


class ProviderNotConfigured(Exception):
    """The bank data provider cannot be used: its application id or private key is missing."""
