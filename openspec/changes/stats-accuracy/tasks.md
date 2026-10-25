# Tasks

TDD: write the scenario test first and see it fail for the right reason. Commit before any mutation check.

## 1. Pending edits

- [x] 1.1 Tests for «Pending transaction is still pending» (flipped), «Edits survive booking» and «No matching booked transaction», then `pop_pending()`, `inherit_edits()` and its use in `Ingest`; unit tests for the matching edge cases (closest date, each pending once, ±3 days); verify and mutation-check

## 2. Currencies

- [x] 2.1 Tests for «Another currency», «Account in another currency», «Everything in euros» and «Dollars left out», then publish the currency in both read models and filter in stats, adding `other_currencies`; verify and mutation-check

## 3. Verification

- [x] 3.1 Regenerate `openapi.json`; ruff, mypy, import-linter, full suite with coverage ≥ 97, spec-coverage meta-test; open the PR and verify CI

## Workflow follow-up

- Archive with spec sync. The frontend change shows the `other_currencies` warning.
