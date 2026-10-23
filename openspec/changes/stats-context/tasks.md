# Tasks

TDD note: refactor. The `stats/financial-summary` characterization tests are the acceptance check; new unit tests are
written first for the stats aggregation rules, which are rewritten from SQL to Python. Commit before any mutation check.

## 1. Published read models

- [x] 1.1 Add `MovementRecord` + `ListMovements` to transactions and `AccountSnapshot` + `AccountSnapshots` to banking, exported by their `public.py`; verify mypy, `lint-imports` and the existing suite pass

## 2. Stats domain and application

- [x] 2.1 Create `app/stats/` and add it to the import contracts; write failing unit tests for the aggregation rules (counted filter, monthly summary, savings incl. withdrawals, spending by category order and uncategorized group, history latest N chronological without empty months, balances by role), then implement `app/stats/domain/`; verify the tests, mypy and `lint-imports` pass
- [x] 2.2 Add the ports and the `MonthlySummary` and `MonthlyHistory` use cases; verify mypy and `lint-imports` pass

## 3. Infrastructure, composition and cleanup

- [x] 3.1 Add the stats router, the port adapters and wiring in `app/bootstrap.py`, store the container in `app.state` in `wire()`, switch `app/main.py` (lifespan, scheduled sync, rules route) to it, and delete `app/stats.py`, `bootstrap.current()` and the import-linter exception
- [x] 3.2 Adapt the tests (scheduled sync with the test container) without changing expected values; verify the whole suite, ruff, mypy and `lint-imports` pass, `git diff tests/` shows no changed expected values, and no `current()` or `ignore_imports` remain

## 4. Documentation and verification

- [ ] 4.1 Update the README architecture section (all contexts migrated, read models published by owners, no exceptions or service locator) and `openspec/config.yaml`'s architecture context (migration complete); verify the paths named exist
- [ ] 4.2 Run `docker compose up -d --build`; verify the API starts, `/api/stats/summary` returns 401 without a session through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync, `skip_specs: true`).
- Then the frontend: its tooling change (lockfile, Biome, Vitest, TanStack Query, generated API types).
