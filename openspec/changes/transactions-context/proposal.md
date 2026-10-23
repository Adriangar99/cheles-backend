# Proposal

## Why

Transactions is the core of the app and still lives in the legacy modules: `app/sync.py` mixes Enable Banking calls,
balance handling and transaction ingestion; `app/main.py` holds the transaction routes; `Transaction` sits in
`app/models.py`. Migrating it removes the largest piece of legacy code, gives the Enable Banking payload translation a
proper home (transactions' own anti-corruption layer, as agreed), and introduces the shared kernel now that two
contexts and legacy code genuinely share concepts.

## What Changes

- **Shared kernel** `app/shared/`: `Money` (amount + currency, no sign semantics), `YearMonth` (`YYYY-MM` with month
  bounds and validation) and typed ids (`AccountId`, `CategoryId`, `TransactionId`). Categorization adopts
  `CategoryId` in its public signatures.
- **`app/transactions/`** bounded context:
  - domain: `Transaction`, the Enable Banking payload translation (signed amount, counterparty, description, dates,
    status, external id), `CounterpartyIban`, transfer detection and derived-field rules (manual category respected);
  - application: ports (transaction repository + unit of work, `OwnAccounts` for own IBANs and account display names,
    `CategorySuggestions` and `CategoryCatalog` for categorization) and use cases: ingest an account's raw
    transactions, latest booked date, list with filters, edit (category, back to automatic, kind, note) and reprocess
    everything;
  - infrastructure: `TransactionRow` (same table, no migration), repository, and the router for
    `GET /api/transactions`, `PATCH /api/transactions/{id}` and `POST /api/reprocess`.
- **Composition root**: implements `OwnAccounts` over the legacy banking tables and the categorization ports over
  `app.categorization.public`, so transactions imports neither legacy code nor categorization.
- **Legacy switch-over**:
  - `app/sync.py` keeps only banking: it reads the window start from transactions, fetches transactions **and
    balances** from Enable Banking, then hands the raw payloads to `ingest` and stores the balance;
  - account IBAN changes and `POST /api/rules` call transactions' reprocess through its public API; the rules route
    orchestrates «create rule, then reprocess» explicitly (no event bus, by decision);
  - stats keeps its SQL over the transactions table through an explicit, commented, transitional import-linter
    exception until stats is migrated.
- `Transaction.account` relationship removed; `bootstrap.current()` is no longer used by sync/reprocess.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Pure refactor (`skip_specs: true`): `transactions/*`, `banking/bank-sync`, `banking/accounts`,
`categorization/transaction-categorization` and `stats/financial-summary` keep every requirement and scenario.

## Impact

- **Bounded contexts**: transactions (migrated); categorization (adopts kernel ids); legacy banking and stats consume
  transactions through `app.transactions.public` (stats with the documented exception).
- **Cross-context events**: none. Cross-context flows are explicit calls orchestrated at the edge.
- **Security surface**: unchanged; the transaction routes keep requiring a session.
- **Database**: same tables; no migration.
- **Behavior**: identical, including the known ⇄ defect. One internal reordering: an account's balances are fetched
  from Enable Banking before its transactions are stored, so a failing balance call still stores nothing for that
  account (as specified in «Transient error»).

### Out of scope

- Migrating banking or stats, and an event bus.
- Fixing the ⇄ defect or other recorded observations (they keep their characterization tests).
