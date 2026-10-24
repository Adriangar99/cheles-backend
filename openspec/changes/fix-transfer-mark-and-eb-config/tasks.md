# Tasks

TDD: write or flip the scenario test first, see it fail, then implement. Commit before any mutation check.

## 1. Manual kind

- [ ] 1.1 Flip the two known-defect tests to «The mark survives a reprocess» / «The mark survives a sync» and add tests for «Remove a manual transfer mark», «Mark a detected transfer as normal», «Automatic kind», «Manual kind» (reprocessing) and «Manual kind kept on ingestion»; verify they fail for the right reason
- [ ] 1.2 Add `kind_manual` to `Transaction` (`derive` respects it, new `set_kind`), the ORM row and repository mapping, Alembic `0002_kind_manual`, `EditTransaction` using `set_kind` with `CategorySuggestions` wired in `bootstrap.py`, and `kind_manual` in `TransactionOut`; regenerate `openapi.json`; verify the transactions tests, the migration tests and the API contract test pass, and mutation-check `set_kind`/`derive`

## 2. Provider not configured

- [ ] 2.1 Add tests for the four «Missing Enable Banking configuration» scenarios; verify they fail (500 today)
- [ ] 2.2 Add `ProviderNotConfigured`, raise it from `EnableBankingClient._jwt()` for a missing application id or unreadable key, map it to 503 in the banking HTTP adapter and to `error=1` in the callback; verify the banking tests pass and mutation-check the mapping

## 3. Verification

- [ ] 3.1 Run ruff, mypy, import-linter and the full pytest suite with coverage (≥ 97); check the spec-coverage meta-test; rebuild the API image and verify `migrate` applies `0002` on the real database without data loss, and that `/api/banks/available` answers 503 with the readable detail on a throwaway stack without `EB_APPLICATION_ID`; open the PR and verify CI

## Workflow follow-up

- Archive the change with spec sync (`/opsx:archive`).
- Frontend change `fix-error-feedback` syncs the new contract (`pnpm api:sync`).
