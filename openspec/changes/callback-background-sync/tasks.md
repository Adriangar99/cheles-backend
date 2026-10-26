# Tasks

TDD: write the scenario test first and see it fail for the right reason.

## 1. Callback without waiting

- [ ] 1.1 Test «The response does not wait for the first sync» (the callback route with a recording `BackgroundTasks`: 303 returned, no transactions requested yet; then the scheduled task syncs), then make `CompleteAuthorization` return the connection id, add `FirstSync` and schedule it from `bank_callback`; verify the bank-connection tests pass, «The first sync fails» included

## 2. Verification

- [ ] 2.1 ruff, mypy, import-linter, full suite with coverage ≥ 97, spec-coverage meta-test; `docker compose up -d --build` and check the callback answers at once; open the PR and verify CI

## Workflow follow-up

- Archive with spec sync. A frontend change may show connections without `last_synced_at` as syncing.
