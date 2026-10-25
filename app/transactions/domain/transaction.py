from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol, get_args

from app.shared.ids import AccountId, CategoryId, TransactionId
from app.shared.money import Money
from app.transactions.domain.bank_payload import NormalizedTransaction, normalize

Kind = Literal["normal", "transfer"]
KINDS: tuple[Kind, ...] = get_args(Kind)
BOOKED = "BOOK"
PENDING = "PDNG"


class CategorySuggester(Protocol):
    """Suggests the automatic category of a movement (provided by categorization through the composition root)."""

    def categorize(self, counterparty: str | None, description: str, is_income: bool) -> CategoryId | None: ...


@dataclass
class Transaction:
    account_id: AccountId
    external_id: str
    booking_date: date
    amount: Money  # negative: money going out
    status: str
    counterparty: str | None
    counterparty_iban: str | None
    description: str
    raw: dict[str, Any] = field(repr=False)
    kind: Kind = "normal"
    kind_manual: bool = False  # set by hand (⇄); sync and reprocessing keep it
    category_id: CategoryId | None = None
    category_manual: bool = False
    note: str | None = None
    id: TransactionId | None = None

    @classmethod
    def from_payload(cls, account_id: AccountId, raw: dict[str, Any]) -> "Transaction":
        data = normalize(raw)
        transaction = cls(
            account_id=account_id,
            external_id=data.external_id,
            booking_date=data.booking_date,
            amount=data.amount,
            status=data.status,
            counterparty=data.counterparty,
            counterparty_iban=None,
            description=data.description,
            raw=raw,
        )
        transaction.refresh_from(raw, data)
        return transaction

    def refresh_from(self, raw: dict[str, Any], data: NormalizedTransaction | None = None) -> None:
        """Takes every bank-derived field from `raw` again; the external id and manual edits are kept."""
        data = data or normalize(raw)
        self.raw = raw
        self.booking_date = data.booking_date
        self.amount = data.amount
        self.status = data.status
        self.counterparty = data.counterparty
        self.counterparty_iban = data.counterparty_iban.value if data.counterparty_iban else None
        self.description = data.description

    def derive(self, own_ibans: Collection[str], suggester: CategorySuggester) -> None:
        """Fields computed from the bank data; a manual kind and a manual category are kept."""
        if not self.kind_manual:
            self.kind = self._automatic_kind(own_ibans)
        if not self.category_manual:
            self.category_id = (
                None
                if self.kind == "transfer"
                else suggester.categorize(self.counterparty, self.description, is_income=self.amount.amount > 0)
            )

    def set_kind(self, kind: Kind, own_ibans: Collection[str], suggester: CategorySuggester) -> None:
        """Sets the kind by hand (⇄). It is only stored as manual when it differs from the automatic one, so asking
        for the automatic kind removes the manual mark."""
        self.kind_manual = kind != self._automatic_kind(own_ibans)
        self.kind = kind
        self.derive(own_ibans, suggester)

    def _automatic_kind(self, own_ibans: Collection[str]) -> Kind:
        return "transfer" if self.counterparty_iban and self.counterparty_iban in own_ibans else "normal"
