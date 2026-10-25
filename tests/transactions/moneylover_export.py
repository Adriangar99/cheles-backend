"""Invented MoneyLover exports for tests (never the owner's real file)."""

HEADER = ["Id", "Fecha", "Categoria", "Cantidad", "Moneda", "Nota", "Cuenta"]


def export(*rows: list[str], header: list[str] = HEADER, encoding: str = "utf-16") -> bytes:
    """A MoneyLover CSV: CRLF lines, fields quoted when they contain a comma, UTF-16 with BOM like the app writes."""

    def field(value: str) -> str:
        return f'"{value}"' if "," in value else value

    lines = [",".join(header), *(",".join(field(v) for v in row) for row in rows)]
    return "\r\n".join(lines).encode(encoding)


def row(
    date: str = "25/10/2026",
    category: str = "Gasolina",
    amount: str = "-47.80",
    note: str = "",
    wallet: str = "Cuenta Principal",
    currency: str = "EUR",
    row_id: str = "1",
) -> list[str]:
    return [row_id, date, category, amount, currency, note, wallet]
