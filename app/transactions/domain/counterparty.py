from dataclasses import dataclass


@dataclass(frozen=True)
class CounterpartyIban:
    """The other party's IBAN, normalized only to be compared with the user's own IBANs.

    Transactions-specific on purpose: banking's own-account IBAN means something else.
    """

    value: str

    @classmethod
    def parse(cls, raw: str | None) -> "CounterpartyIban | None":
        return cls(raw.replace(" ", "").upper()) if raw else None
