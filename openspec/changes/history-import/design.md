# Design

## Context

The owner's export (`~/Downloads/628e…csv`, not versioned) has 1338 rows from May 2025 to October 2026 in three wallets
(«Cuenta Principal», «Cuenta Ahorros», «Revolut»), all in EUR, 32 categories of which only 4 share a name with Cheles'
16. Format: UTF-16 LE with BOM, CRLF, comma separated, quoted fields when they contain commas, `dd/mm/yyyy`, amounts
like `-47.80`. `Id` counts rows of that export (1 is the newest) and changes on the next export.

Decisions taken with the owner: skip by date cutoff against the bank; import from «bancos» with a preview; categories
by a fixed equivalence table, then name, then rules.

## Goals / Non-Goals

**Goals:** months before the bank connection appear in every screen; importing twice, or a newer export, does not
duplicate; nothing the bank brought is duplicated; transfers between own wallets do not count as income or spending.

**Non-Goals:** other formats now; a UI to edit equivalences; balances for imported accounts.

## Decisions

### Reader as an anti-corruption layer
`app/transactions/domain/moneylover.py` parses bytes into `ImportedRow(wallet, date, amount: Money, category, note,
external_id)`. Encoding: BOM decides UTF-16/UTF-8 (UTF-8 without BOM accepted). The header must contain the seven
columns (any order); otherwise `UnrecognizedFile` → 422 «No reconozco este fichero: falta la columna <x>». A bad row
(date, amount) → 422 naming the line. Pure, so it is unit tested with invented fixtures.

### Stable id
`ml:` + SHA-256 of `wallet|date|amount|currency|category|note|n` (first 32 hex), where `n` numbers identical rows within
the file (two coffees of 1,50 € on the same day stay two). A newer export yields the same ids for the same rows. The
unique `(account_id, external_id)` constraint already guards duplicates.

### Cutoff against the bank
For a target account with bank transactions, `bank_since` is the earliest `booking_date` among its `source = bank`
transactions; rows dated on or after it are skipped and counted. New accounts and accounts without bank transactions
have no cutoff. Chosen over row matching because MoneyLover has no counterparty to compare.

### Targets
The request maps each wallet to an existing account id, `"new"` (an account without a bank named after the wallet,
role `main`, created through banking's public API) or `null` (not imported). Wallets missing from the map are not
imported. Unknown account ids → 422.

### Transactions from rows
`source = import`, status `BOOK`, `counterparty = None`, `description` = note or, when empty, the MoneyLover category,
`raw` = the row as read (for reference). Category: equivalence table → same name (casefold, accents removed) → rules on
the description; the first two are stored as manual (they come from the user's own choice in MoneyLover), the third as
automatic. «Transferencia entrante»/«Transferencia saliente» → `kind = transfer`, `kind_manual = true`, no category.

Equivalence table (MoneyLover built-ins → Cheles): Salario→Nómina; Alquiler, Mantenimiento del hogar→Vivienda;
Comida y bebida→Supermercado; Comer en casa o fuera→Restaurantes; Gasolina, Mantenimiento de vehículos→Transporte;
Factura de agua/electricidad/gas/internet/teléfono, Otras facturas de servicios→Suministros; Servicios de
entretenimiento→Suscripciones; Diversión, Gimnasio→Ocio; Chequeos médicos→Salud; Seguros→Impuestos y comisiones;
Artículos para el hogar, Objetos personales, Regalos & Donaciones, Mascotas→Compras. A target missing from the
catalog (the user deleted it) falls through to name and rules.

### Preview and import share one computation
`PlanImport` reads, resolves categories and cutoffs and returns the plan; preview returns it, import executes it in
one unit of work (creating new accounts first). The file is sent as base64 in JSON (`{"file": …, "accounts": {…}}`)
so the typed client stays simple; limit 5 MB decoded → 413.

### Reprocessing
`ReprocessAll` skips `refresh_from(raw)` for `source = import` and still calls `derive` (manual fields kept).
Ingestion never meets imported transactions: their ids start with `ml:`.

## Risks / Trade-offs

- [A wallet mapped to a bank account whose bank history starts later than MoneyLover stops] → a gap; the preview shows
  both date ranges so the owner sees it.
- [Rows edited in MoneyLover after an import get a new id] → they would be imported again; the preview counts «ya
  importados» so it shows. Acceptable for a one-off history import.
- [Rules on notes are weaker than on bank counterparties] → unmatched categories are listed in the preview.

## Migration Plan

`0003_transaction_source` adds `source` (`String(8)`, server default `bank`). Rollback: downgrade drops the column
(imported transactions would then look like bank ones; delete them first).
