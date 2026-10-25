"""Anti-corruption layer: turns a MoneyLover CSV export into rows to import.

MoneyLover writes UTF-16 with a BOM (UTF-8 is accepted too), comma separated, dates as dd/mm/yyyy and signed amounts
with a decimal point. Its `Id` is renumbered on every export, so each row is identified by its content instead.
"""

import csv
import hashlib
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.shared.money import Money

COLUMNS = ("Id", "Fecha", "Categoria", "Cantidad", "Moneda", "Nota", "Cuenta")
ADJUSTMENT_NOTE = "ajuste"


class UnrecognizedFile(Exception):
    """The file is not a MoneyLover export; the message is shown to the user."""


class UnreadableRow(Exception):
    """A row of the export has a date or amount that cannot be read; the message is shown to the user."""


@dataclass(frozen=True)
class ImportedRow:
    line: int  # line of the file, the header being line 1
    wallet: str
    booking_date: date
    amount: Money
    category: str
    note: str
    external_id: str
    raw: dict[str, str] = field(repr=False)

    @property
    def is_adjustment(self) -> bool:
        """MoneyLover's balance corrections: not money that came in or went out."""
        return self.note.strip().casefold() == ADJUSTMENT_NOTE


def _decode(content: bytes) -> str:
    try:
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return content.decode("utf-16")
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnrecognizedFile("No reconozco este fichero: no es un CSV de texto") from error


def _date(text: str, line: int) -> date:
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date()
    except ValueError as error:
        raise UnreadableRow(f"Línea {line}: la fecha «{text}» no es válida") from error


def _amount(text: str, line: int) -> Decimal:
    try:
        amount = Decimal(text.strip())
    except InvalidOperation as error:
        raise UnreadableRow(f"Línea {line}: el importe «{text}» no es válido") from error
    if not amount.is_finite():
        raise UnreadableRow(f"Línea {line}: el importe «{text}» no es válido")
    return amount


def read_export(content: bytes) -> list[ImportedRow]:
    """Every row of the export, in file order. Identical rows get distinct ids by their position among themselves."""
    reader = csv.DictReader(io.StringIO(_decode(content), newline=""))
    missing = [column for column in COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise UnrecognizedFile(f"No reconozco este fichero: falta la columna {missing[0]}")
    seen: Counter[str] = Counter()
    rows: list[ImportedRow] = []
    for index, raw in enumerate(reader):
        line = index + 2
        booking_date = _date(raw["Fecha"] or "", line)
        amount = Money(_amount(raw["Cantidad"] or "", line), (raw["Moneda"] or "EUR").strip())
        wallet, category, note = [(raw[c] or "").strip() for c in ("Cuenta", "Categoria", "Nota")]
        content_key = "|".join([wallet, booking_date.isoformat(), str(amount.amount), amount.currency, category, note])
        occurrence = seen[content_key]
        seen[content_key] += 1
        digest = hashlib.sha256(f"{content_key}|{occurrence}".encode()).hexdigest()[:32]
        rows.append(
            ImportedRow(
                line=line,
                wallet=wallet,
                booking_date=booking_date,
                amount=amount,
                category=category,
                note=note,
                external_id=f"ml:{digest}",
                raw={column: raw[column] or "" for column in COLUMNS},
            )
        )
    return rows
