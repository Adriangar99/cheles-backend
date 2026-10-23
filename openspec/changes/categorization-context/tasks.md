# Tasks

TDD note: refactor. The characterization suite (categorization, transactions, stats, banking) must stay green after
each group. New unit tests are written first only for `CategorizationPolicy`, the one piece of real logic being
rewritten; moved code is covered by the characterization tests. Commit before any mutation check.

## 1. Domain and application

- [x] 1.1 Create `app/categorization/{domain,application,infrastructure}` and `public.py`, and generalize the import-linter contracts to both contexts plus the cross-context «public only» contract; verify `uv run lint-imports` passes
- [ ] 1.2 Write failing unit tests for `CategorizationPolicy` (first matching rule by ascending priority then creation order, case-insensitive match on « counterparty description », trailing-space patterns, fallbacks: Bizum income, other income, other expense for debits and zero), then implement it with `Category`, `Rule`, the default catalog and `UnknownCategory`; verify the tests pass
- [ ] 1.3 Add the ports and use cases (`SeedDefaultCatalog`, `ListCategories`, `CreateRule`, `CategoryExists`, `LoadPolicy`, `CategoryLabels`, `CategorizationServices`); verify `uv run mypy` and `uv run lint-imports` pass

## 2. Infrastructure and legacy switch-over

- [ ] 2.1 Move `Category`/`Rule` to `CategoryRow`/`RuleRow` in `app/categorization/infrastructure/orm.py`, add the repositories and unit of work, remove the `Transaction.category` relationship, and register the module in `migrations/env.py`; verify `uv run alembic check` against a migrated scratch database reports no changes
- [ ] 2.2 Add the `GET /api/categories` router with its placeholder dependency, extend `Container`/`wire()` with categorization services and the transitional `bootstrap.current()`, and switch the legacy code (lifespan seeding, `POST /api/rules`, transaction PATCH validation, sync and reprocess, stats labels) to `app.categorization.public`; delete `app/categorize.py`
- [ ] 2.3 Adapt the characterization tests (imports, conftest seeding, category-name lookups instead of the removed relationship) without changing any expected value; verify the whole suite passes, ruff, mypy and lint-imports pass, and `git diff tests/` shows no changed expected values

## 3. Documentation and verification

- [ ] 3.1 Update the README architecture section (categorization migrated, `bootstrap.current()` as a transitional accessor for legacy code) and the import-contracts description; verify the paths it names exist
- [ ] 3.2 Run `docker compose up -d --build`; verify the API starts and `/api/categories` returns 401 without a session through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync, `skip_specs: true`).
- Next change: migrate transactions (introduces the shared kernel and the event bus, replacing the legacy rules route orchestration and `bootstrap.current()` for transactions).
