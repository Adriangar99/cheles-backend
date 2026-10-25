"""Importing history from another app's export: which rows go where, and with which category.

Pure: the plan is computed from the rows read, the chosen targets and what the database already holds.
"""

import unicodedata
from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from app.shared.ids import AccountId, CategoryId
from app.transactions.domain.moneylover import ImportedRow

NEW: Literal["new"] = "new"
Target = AccountId | Literal["new"] | None

# MoneyLover's built-in categories → Cheles' default catalog. Users' own MoneyLover categories are not here.
EQUIVALENTS: dict[str, str] = {
    "Salario": "Nómina",
    "Alquiler": "Vivienda",
    "Mantenimiento del hogar": "Vivienda",
    "Comida y bebida": "Supermercado",
    "Comer en casa o fuera": "Restaurantes",
    "Gasolina": "Transporte",
    "Mantenimiento de vehículos": "Transporte",
    "Factura de agua": "Suministros",
    "Factura de electricidad": "Suministros",
    "Factura de gas": "Suministros",
    "Factura de internet": "Suministros",
    "Factura de teléfono": "Suministros",
    "Otras facturas de servicios": "Suministros",
    "Servicios de entretenimiento": "Suscripciones",
    "Diversión": "Ocio",
    "Gimnasio": "Ocio",
    "Chequeos médicos": "Salud",
    "Seguros": "Impuestos y comisiones",
    "Artículos para el hogar": "Compras",
    "Objetos personales": "Compras",
    "Regalos & Donaciones": "Compras",
    "Mascotas": "Compras",
}


def name_key(name: str) -> str:
    """Category names compared ignoring case, accents and surrounding spaces."""
    decomposed = unicodedata.normalize("NFKD", name.strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


_EQUIVALENTS = {name_key(source): target for source, target in EQUIVALENTS.items()}


def chosen_category(category: str, catalog: Mapping[str, CategoryId]) -> CategoryId | None:
    """The Cheles category the user's MoneyLover category stands for: by the equivalence table, else by the same name.
    `catalog` maps `name_key(name)` to the id. None leaves the category to the automatic rules."""
    key = name_key(category)
    equivalent = _EQUIVALENTS.get(key)
    if equivalent is not None and name_key(equivalent) in catalog:
        return catalog[name_key(equivalent)]
    return catalog.get(key)


@dataclass
class WalletPlan:
    name: str
    target: Target
    rows: list[ImportedRow] = field(default_factory=list)
    bank_since: date | None = None
    to_import: list[ImportedRow] = field(default_factory=list)
    skipped: int = 0
    already_imported: int = 0
    adjustments: int = 0

    @property
    def first_date(self) -> date:
        return min(r.booking_date for r in self.rows)

    @property
    def last_date(self) -> date:
        return max(r.booking_date for r in self.rows)


@dataclass
class ImportPlan:
    wallets: list[WalletPlan]
    unmatched_categories: list[tuple[str, int]]


def plan_import(
    rows: list[ImportedRow],
    targets: Mapping[str, Target],
    bank_since: Mapping[AccountId, date | None],
    already_imported: Mapping[AccountId, Collection[str]],
    catalog: Mapping[str, CategoryId],
) -> ImportPlan:
    """Per wallet (in order of first appearance): balance adjustments are never imported; with an existing account as
    target, rows on or after its first bank transaction are skipped (the bank has them) and rows imported before are
    counted apart. `bank_since` and `already_imported` describe the existing target accounts."""
    wallets: dict[str, WalletPlan] = {}
    for row in rows:
        plan = wallets.setdefault(row.wallet, WalletPlan(row.wallet, targets.get(row.wallet)))
        plan.rows.append(row)
    for plan in wallets.values():
        existing = plan.target if plan.target not in (None, NEW) else None
        plan.bank_since = bank_since.get(existing) if existing is not None else None
        known = already_imported.get(existing, ()) if existing is not None else ()
        for row in plan.rows:
            if row.is_adjustment:
                plan.adjustments += 1
            elif plan.target is None:
                continue
            elif plan.bank_since is not None and row.booking_date >= plan.bank_since:
                plan.skipped += 1
            elif row.external_id in known:
                plan.already_imported += 1
            else:
                plan.to_import.append(row)
    unmatched = Counter(
        row.category for row in rows if not row.is_adjustment and chosen_category(row.category, catalog) is None
    )
    return ImportPlan(list(wallets.values()), sorted(unmatched.items()))
