# Tasks

TDD note: tasks for new behavior (`platform/service-runtime`) start with a failing test. Characterization tasks write
tests for existing behavior, which must pass against the current code; a failing characterization test means the spec
misdescribes the code, so the spec is corrected (never the code) and the mismatch is reported.

## 1. Toolchain with uv

- [x] 1.1 Create `pyproject.toml` (runtime deps at today's exact versions plus `alembic`; `dev` group with pytest, pytest-cov, testcontainers[postgres], time-machine, ruff, mypy) and `.python-version` (3.12); generate `uv.lock`; delete `requirements.txt`; verify `uv sync --frozen` succeeds and `uv run python -c "import app.models"` works with `DATABASE_URL` set
- [x] 1.2 Rewrite the `Dockerfile` to install with a pinned `uv` binary (`uv sync --frozen --no-dev`) and run as the `cheles` user; verify `docker compose build api` succeeds and the image contains no dev dependencies (`docker run --rm cheles-api python -c "import pytest"` fails)

## 2. Static checks

- [x] 2.1 Configure ruff in `pyproject.toml` (line length 120; rules E, F, W, I, UP, B, SIM, RUF) and run `ruff format` over the codebase as an isolated formatting commit; verify `uv run ruff format --check .` passes
- [x] 2.2 Fix `ruff check` findings without changing behavior; verify `uv run ruff check .` passes
- [x] 2.3 Configure mypy strict (`app`, `migrations`, `tests`; `pydantic.mypy` plugin; `ignore_missing_imports` only for untyped third-party packages) and fix the current errors with annotations and narrowing only; verify `uv run mypy` reports no errors

## 3. Alembic baseline

- [x] 3.1 Add `alembic.ini` and `migrations/env.py` reading the URL from settings and `target_metadata` from `app.db.Base`; verify `uv run alembic current` connects to a throwaway Postgres
- [x] 3.2 Autogenerate `0001_baseline` against an empty database and review it by hand; verify `pg_dump --schema-only` of a database built by `alembic upgrade head` equals one built by `create_all`, apart from `alembic_version`

## 4. Test harness

- [x] 4.1 Write `tests/conftest.py`: session-scoped Postgres 16 testcontainer started before importing `app`, `DATABASE_URL` exported, `alembic upgrade head` once, per-test truncation + category re-seed + throttle reset, and a `client` fixture (`TestClient` as context manager); verify a smoke test hitting `/api/health` passes with `uv run pytest`
- [x] 4.2 Add `tests/fakes.py` with `FakeEnableBanking` (banks, auth start, sessions, accounts, paged transactions, balances, recorded calls, error injection) and a fixture that installs it in `app.main` and `app.sync`; add helpers to log in (TOTP from the stored secret), to complete a bank connection, and the test-only client-IP ASGI wrapper; verify with a test that connects a fake bank end to end
- [x] 4.3 Configure pytest and coverage in `pyproject.toml` (`testpaths`, `--strict-markers`, coverage source `app`); verify `uv run pytest --cov` prints a coverage report

## 5. Service runtime (new behavior, TDD)

- [x] 5.1 Write failing tests for «Missing database URL» (API and CLI started in a subprocess without `DATABASE_URL` exit with an error naming it); make `Settings.database_url` required and document it in `.env.example`; verify the tests pass
- [x] 5.2 Write failing tests for «Empty database», «Database already up to date» and «Existing database created before migrations» (each against its own throwaway database, the last one built with `create_all` and seeded with rows); implement `python -m app.cli migrate` (stamp baseline when tables exist without `alembic_version`, then `upgrade head`); verify the tests pass and the rows survive
- [x] 5.3 Write the «Health check» test; verify it passes (the schema comparison from 3.2 stays a one-off manual check, not a test)
- [x] 5.4 Remove `create_all` from the API lifespan and from `create-user` (which now runs the migrate routine first), and change the Dockerfile `CMD` to run `migrate` before `exec uvicorn`; verify the whole suite still passes and `create-user` works on an empty database in a test

## 6. Characterization tests (existing behavior)

- [x] 6.1 `tests/identity/test_user_authentication.py`: one test per scenario of `identity/user-authentication` (CLI creation, login, TOTP window, cookie attributes, hashed token, purge, protected endpoints, logout, throttle with sliding window and per-IP isolation); verify all pass
- [x] 6.2 `tests/banking/test_bank_connection.py` and `tests/banking/test_accounts.py`: one test per scenario of `banking/bank-connection` and `banking/accounts`; verify all pass
- [x] 6.3 `tests/banking/test_bank_sync.py`: one test per scenario of `banking/bank-sync`, including the scheduled job (configured hours, active connections only, errors logged) by calling the scheduled function directly; verify all pass
- [x] 6.4 `tests/transactions/test_transaction_ingestion.py`, `test_transaction_management.py` and `test_reprocessing.py`: one test per scenario, including the known-defect scenarios of the ⇄ mark; verify all pass
- [x] 6.5 `tests/categorization/test_transaction_categorization.py`: one test per scenario of `categorization/transaction-categorization`; verify all pass
- [x] 6.6 `tests/stats/test_financial_summary.py`: one test per scenario of `stats/financial-summary`; verify all pass
- [x] 6.7 Cross-check scenarios against tests with a script listing every `#### Scenario:` title in `openspec/specs/` and in this change's spec that has no test docstring quoting it; verify the list is empty; set coverage `fail_under` to the measured value rounded down

## 7. Continuous integration

- [x] 7.1 Add `.github/workflows/ci.yml` (push to `main` and pull requests; pinned `setup-uv`; `uv sync --frozen`; ruff check, ruff format --check, mypy, pytest with coverage); verify the workflow passes on the pull request for this branch

## 8. Documentation and verification

- [x] 8.1 Update `README.md` with a Development section (uv setup, running tests, lint/type checks, creating and applying migrations, `DATABASE_URL` requirement); verify each documented command runs as written
- [x] 8.2 Before the first start of the new image against the real `cheles_db-data` volume, diff its `pg_dump --schema-only` against a freshly migrated database; verify they are identical (pause and report if not)
- [x] 8.3 Run `docker compose up -d --build`; verify the logs show the baseline being stamped, `alembic_version` holds `0001_baseline`, `/api/health` returns `{"ok":true}` and the web app still reaches the API through `http://127.0.0.1:3000/api/health`

## Workflow follow-up

- Archive the change (`/opsx:archive`) so `platform/service-runtime` moves to `openspec/specs/`.
- Next change: hexagonal skeleton (shared kernel, event bus, composition root, import-linter).
