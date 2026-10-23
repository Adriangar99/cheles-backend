# Tasks

TDD note: refactor. The characterization suite must stay green after each group; new unit tests are written first only
for `YearMonth`. Commit before any mutation check.

## 1. Shared kernel

- [x] 1.1 Write failing unit tests for `YearMonth` (parses `2026-10`, rejects `2026-9` and `09-2026`, bounds of October and of December → next January), then add `app/shared/{money,year_month,ids}.py` and a contract that keeps `app.shared` free of other `app` modules and frameworks; verify the tests and `lint-imports` pass
- [x] 1.2 Switch categorization's public signatures to `CategoryId`; verify mypy and the categorization tests pass

## 2. Transactions domain and application

- [x] 2.1 Create `app/transactions/` and extend the import contracts to it (layers, framework-free core, no legacy incl. `app.legacy_bridge`, public-only between contexts); move the payload translation, `CounterpartyIban` and the derivation rules into the domain unchanged; verify mypy and `lint-imports` pass
- [x] 2.2 Add the ports and the use cases (`Ingest`, `LatestBookedDate`, `ListTransactions`, `EditTransaction`, `ReprocessAll`); verify mypy and `lint-imports` pass

## 3. Infrastructure, composition and legacy switch-over

- [x] 3.1 Move `Transaction` to `TransactionRow` in `app/transactions/infrastructure/orm.py` (no `account` relationship), add the repository and unit of work, register the module in `migrations/env.py`; verify `alembic check` on a migrated scratch database reports no changes
- [x] 3.2 Add the transactions router (list, patch, reprocess), `app/legacy_bridge.py` (`OwnAccounts`), the categorization port adapters and the `Container`/`wire()` wiring; switch `app/sync.py` to banking-only (window, fetch transactions and balances, ingest, balance), the account IBAN change and `POST /api/rules` to `app.transactions.public`, and add the commented stats exception; remove the moved code from `app/sync.py` and `app/main.py`
- [x] 3.3 Adapt the characterization tests' imports/fixtures without changing expected values; verify the whole suite, ruff, mypy and `lint-imports` pass, `git diff tests/` shows no changed expected values, and `bootstrap.current()` is no longer used by `app/sync.py`

## 4. Documentation and verification

- [x] 4.1 Update the README architecture section (transactions and the shared kernel, `legacy_bridge`, the stats exception, orchestrated rules route); verify the paths it names exist
- [x] 4.2 Run `docker compose up -d --build`; verify the API starts, `/api/transactions` returns 401 without a session through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync, `skip_specs: true`).
- Next change: migrate banking (moves `OwnAccounts` to banking's public API and removes `app/legacy_bridge.py`).
