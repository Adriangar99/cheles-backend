# Tasks

TDD note: refactor. The characterization suite must stay green after each group; new unit tests are written first only
for the event bus and the reconnection matching. Commit before any mutation check.

## 1. Event bus and banking domain

- [x] 1.1 Write failing unit tests for `InMemoryEventBus` (subscribers of the published type run, others do not; a failing handler is logged and does not stop the rest), then implement `app/shared/events.py`; verify the tests and `lint-imports` pass
- [x] 1.2 Create `app/banking/` and extend the import contracts to it; write failing unit tests for reconnection matching (identification hash first, then normalized IBAN, new account otherwise; an incoming account without IBAN keeps the stored one), then implement the banking domain (`BankConnection`, `PendingAuthorization`, `Account`, `Iban`, sync policy, reconnection, `AccountIbanChanged`, errors); verify the tests, mypy and `lint-imports` pass

## 2. Banking application

- [x] 2.1 Add the ports and use cases (`ListConnections`, `ListAvailableBanks`, `StartAuthorization`, `CompleteAuthorization`, `SyncConnection`, `SyncAll`, `UpdateAccount` publishing `AccountIbanChanged` after commit, `OwnAccountIbans`, `AccountDisplayNames`); verify mypy and `lint-imports` pass

## 3. Infrastructure, composition and legacy removal

- [x] 3.1 Move `PendingAuth`/`BankConnection`/`Account` to banking ORM rows, add the repositories, move the Enable Banking client to `app/banking/infrastructure/enable_banking.py` raising `ProviderError`, and register the rows in `migrations/env.py`; verify `alembic check` on a migrated scratch database reports no changes
- [x] 3.2 Add the banking router, the `Container`/`wire()` wiring (provider field, event bus and the `AccountIbanChanged` subscription, transactions ↔ banking adapters, scheduled sync), extend the stats exception, and delete `app/models.py`, `app/sync.py`, `app/enablebanking.py`, `app/legacy_bridge.py` and the bank/account routes in `app/main.py`
- [x] 3.3 Adapt the characterization tests (ORM imports, fake provider through the container, pagination test, scheduled-sync stub) without changing expected values; verify the whole suite, ruff, mypy and `lint-imports` pass, and `git diff tests/` shows no changed expected values

## 4. Documentation and verification

- [x] 4.1 Update the README architecture section (banking migrated, event bus and its wiring, remaining legacy modules, stats exception); verify the paths it names exist
- [ ] 4.2 Run `docker compose up -d --build`; verify the API starts, `/api/banks` returns 401 without a session through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync, `skip_specs: true`).
- Next change: migrate stats as its own read model (removes the import-linter exception and `bootstrap.current()`).
