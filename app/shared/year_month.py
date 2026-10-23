import re
from dataclasses import dataclass
from datetime import date

_FORMAT = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True, order=True)
class YearMonth:
    """A calendar month, written `YYYY-MM`."""

    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> "YearMonth":
        match = _FORMAT.match(text)
        if not match:
            raise ValueError(f"Not a YYYY-MM month: {text!r}")
        return cls(int(match.group(1)), int(match.group(2)))

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:
        """First day of the following month (exclusive bound)."""
        return date(self.year + (self.month == 12), self.month % 12 + 1, 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
