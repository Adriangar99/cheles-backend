from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    """An amount in a currency. The sign has no meaning here; each context decides what it represents."""

    amount: Decimal
    currency: str = "EUR"
