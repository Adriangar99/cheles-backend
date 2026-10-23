# Tasks

This change adds no behavior, so there are no TDD tasks; the scenarios become characterization tests in the next
change.

## 1. Review specs against the code

- [x] 1.1 Re-check `identity/user-authentication` against `app/security.py`, `app/cli.py` and the auth routes in `app/main.py`; verify every scenario matches the code path (fix the spec, not the code)
- [x] 1.2 Re-check `banking/bank-connection`, `banking/bank-sync` and `banking/accounts` against `app/main.py`, `app/sync.py` and `app/enablebanking.py`; verify every scenario matches the code path
- [x] 1.3 Re-check `transactions/*` and `categorization/transaction-categorization` against `app/sync.py`, `app/categorize.py` and the transaction routes; verify every scenario matches the code path
- [x] 1.4 Re-check `stats/financial-summary` against `app/stats.py`; verify every scenario matches the queries
- [x] 1.5 Run `openspec validate specs-base --strict` and verify it reports the change as valid

## 2. Documentation

- [x] 2.1 Translate `README.md` to English keeping its content (setup, Enable Banking onboarding, account roles, security, OpenSpec workflow), and add a short "Language" note (code and docs in English, UI in Spanish); verify the documented commands are unchanged

## 3. Verification

- [x] 3.1 Run `git diff --stat` and verify only `openspec/` and `README.md` changed
- [x] 3.2 Run `docker compose up -d --build` and verify the API starts and `/api/health` answers inside the container (`docker compose exec api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/health').read())"`)

## Workflow follow-up

- Archive the change (`/opsx:archive`) so the specs move to `openspec/specs/`.
- Next change: `tooling-and-characterization` (uv, ruff, mypy, pytest + testcontainers, Alembic baseline, characterization tests from these scenarios, import-linter).
