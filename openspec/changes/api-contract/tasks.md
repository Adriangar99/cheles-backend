# Tasks

TDD note: the existing characterization suite is the acceptance check (identical JSON). The drift test is written
first, failing until the contract file exists.

## 1. Response models

- [x] 1.1 Add `app/http_types.py` (`JsonDecimal`, `JsonDateTime`) and declare response models for the identity, categorization and transactions routes; verify the suite, mypy and `lint-imports` pass
- [x] 1.2 Declare response models for the banking and stats routes and the composition-edge routes in `app/main.py`; verify the suite, mypy and `lint-imports` pass, and that every route in `app.openapi()` except the bank callback has a non-empty 200 response schema

## 2. Versioned contract

- [x] 2.1 Write the failing drift test (`tests/platform/test_api_contract.py`), then add `python -m app.cli openapi` and generate `openapi.json`; verify the test passes and fails again after a deliberate route change that is reverted
- [x] 2.2 Document regenerating the contract in the README and add the check to the Development section; verify the command runs as documented

## 3. Verification

- [ ] 3.1 Run `docker compose up -d --build`; verify the API starts, a login with wrong credentials still returns 401 «Datos incorrectos» through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync, `skip_specs: true`).
- Then cheles-frontend's tooling change copies `openapi.json` and generates its types from it.
