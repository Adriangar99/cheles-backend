# Tasks

TDD: write the scenario test first and see it fail for the right reason. Commit before any mutation check.

## 1. Sync and listing

- [ ] 1.1 Test «Syncing an expired connection» and «Country of a connection», then skip non-active connections in `SyncConnection` and expose `country`; verify the bank-sync and accounts tests pass

## 2. Removing a connection

- [ ] 2.1 Tests for «Remove a connection», «Enable Banking fails to close the session», «Unknown connection» and «Reconnecting after removing», then add `RemoveConnection`, `DELETE /api/banks/{id}` and the revoked filter in the listing; verify and mutation-check

## 3. Pending authorizations

- [ ] 3.1 Tests for «Old pending authorization» and «Recent pending authorization» (time-machine), then add `created_at` to the domain and the cleanup in `StartAuthorization`; verify

## 4. Verification

- [ ] 4.1 Regenerate `openapi.json`; ruff, mypy, import-linter, full suite with coverage ≥ 97, spec-coverage meta-test; open the PR and verify CI

## Workflow follow-up

- Archive with spec sync. The frontend change consumes `country` and `DELETE /api/banks/{id}`.
