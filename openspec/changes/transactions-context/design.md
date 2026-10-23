# Design

## Context

See proposal.md. Current code:

- `app/sync.py`: `normalize_transaction(raw)` (signed amount, counterparty by direction, description fallback,
  booking/value/transaction date, status, external id `ref:`/`id:`/`h:`), `own_ibans(db)`, `apply_derived_fields`
  (transfer if counterparty IBAN is an own IBAN; category from the policy unless manual), `sync_account` (window from
  the latest `BOOK` date − 10 days or `initial_history_days`, fetch, delete `PDNG`, upsert by `(account_id,
  external_id)`, derive, fetch balances, commit), `sync_connection`/`sync_all` (banking), `reprocess_all`.
- `app/main.py`: transaction listing (joins `Account` for the display name), PATCH (manual category, back to automatic
  → reprocess, kind, note), `/api/reprocess`, `/api/rules`, account PATCH (IBAN change → reprocess), and the callback
  that runs the first sync.
- `app/stats.py`: aggregates over `transactions` joined with `accounts` (roles).

## Goals / Non-Goals

**Goals:** identical behavior; transactions depends only on the kernel and its own ports; legacy code uses
`app.transactions.public`; no `bootstrap.current()` in sync/reprocess.

**Non-Goals:** migrating banking or stats; an event bus; behavior fixes.

## Decisions

### Shared kernel (`app/shared/`), justified by meaning
- `Money(amount: Decimal, currency: str)`: the same concept in transactions, banking balances and stats totals. It
  carries no sign semantics; transactions decides that negative means money out.
- `YearMonth`: a calendar period with `parse()` (strict `YYYY-MM`), `start`, `end` (first day of the next month). It
  means the same everywhere it is used (transaction filter, stats).
- `AccountId`, `CategoryId`, `TransactionId` as `NewType(int)`: cross-context references with type safety and no
  runtime cost.
- Kept out of the kernel because their meaning differs per context: `Iban` (banking, identifies an own account) vs
  `CounterpartyIban` (transactions, only compared against own IBANs); the signed amount interpretation; categorization's
  `is_income`.
- A new contract forbids `app.shared` from importing any other `app` module or framework.

### Transactions layout

```
app/transactions/
  domain/
    transaction.py     # Transaction (entity), Kind, Status, derive(): transfer + automatic category rules
    bank_payload.py    # ACL: translate an Enable Banking raw payload -> NormalizedTransaction (pure)
    counterparty.py    # CounterpartyIban (normalized: no spaces, uppercase)
  application/
    ports.py           # TransactionRepository, UnitOfWork, OwnAccounts, CategorySuggestions, CategoryCatalog
    use_cases.py       # Ingest, LatestBookedDate, ListTransactions, EditTransaction, ReprocessAll (+ services)
  infrastructure/
    orm.py             # TransactionRow (same table)
    repositories.py    # SQL repository (filters, ilike search, ordering) + unit of work
    http.py            # GET/PATCH /api/transactions, POST /api/reprocess, placeholder dependency
  public.py            # TransactionsServices, IngestResult-free API used by legacy code
```

### Ports filled at the composition root
- `OwnAccounts.ibans()` and `OwnAccounts.display_names(account_ids)`: implemented in `app/legacy_bridge.py` over the
  legacy banking models (`Account.iban`, `alias or name`). Contexts may not import it (added to the no-legacy
  contract); only `app.bootstrap` does.
- `CategorySuggestions.load()` returns an object with `categorize(counterparty, description, is_income)`;
  `CategoryCatalog.exists(id)`. Both adapted from `app.categorization.public` in the bootstrap, so transactions does
  not depend on categorization at all.

### Ingest and the sync split
- `Ingest(account_id, raws)` runs in one unit of work: delete the account's `PDNG` rows, upsert each normalized payload
  by `(account_id, external_id)` (updates overwrite normalized fields, keep manual edits), derive kind/category, commit,
  and return the number created. `LatestBookedDate(account_id)` provides the window start for banking.
- Banking's `sync_account` becomes: window from `LatestBookedDate`, `get_transactions`, `get_balances`, `Ingest`,
  then set the balance in the legacy session and commit. Fetching balances before ingesting keeps «Transient error»
  intact: if either Enable Banking call fails, nothing is written for that account. Earlier accounts of the same
  connection stay committed, as today.
- The first sync in the bank callback and the scheduled sync keep calling legacy `sync_connection`.

### Reprocess and edits
- `ReprocessAll()` recomputes normalized fields (except `external_id`) and derived fields for every transaction and
  returns the count; manual categories and notes survive; kind is always recomputed (known ⇄ defect preserved).
- `EditTransaction` validates the category through `CategoryCatalog` (400 «Categoría inexistente»), and a
  `clear_category` request triggers `ReprocessAll` after committing, as today.
- `POST /api/rules` stays in `app/main.py` as an explicit orchestration: `categorization.create_rule` then
  `transactions.reprocess_all`, returning `{"processed": N}`. Account IBAN changes call `transactions.reprocess_all`
  after the legacy commit.

### Listing
`ListTransactions(criteria)` filters in SQL (month via `YearMonth`, case-insensitive `ilike` on counterparty or
description, category, account, kind), orders by date desc then id desc, applies limit/offset, and fills the
`account` field from `OwnAccounts.display_names`. The serialized shape is unchanged.

### Stats exception
`app.stats` keeps importing `TransactionRow` for its aggregate SQL. The «legacy → public only» contract lists it in
`ignore_imports` with a comment pointing to the stats migration. No other legacy module gets an exception.

### Tests
Characterization tests keep every expected value; imports move to `TransactionRow` (aliased as `Transaction`). New
unit tests only for `YearMonth` (strict parsing, December → January bounds), the one kernel piece with edge cases the
HTTP suite does not cover. The payload translation and derivation move without logic changes and stay covered by the
ingestion, sync and reprocessing characterization tests.

## Risks / Trade-offs

- [Ingestion split across two transactions (transactions' unit of work, then the legacy balance commit)] → If the
  balance write itself fails after a successful ingest, transactions are stored without the new balance; the next
  sync fixes it. Enable Banking failures, the realistic case, still store nothing.
- [Stats exception] → Explicit, single, documented, removed with the stats migration.
- [legacy_bridge reading banking tables] → It is the anti-corruption point for legacy banking and disappears when
  banking is migrated (its port implementation moves to banking's public API).

## Migration Plan

Refactor only; rebuild the image. No data or schema change.
