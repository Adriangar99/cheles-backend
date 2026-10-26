# Tasks

TDD: write the scenario test first and see it fail for the right reason.

## 1. Title

- [ ] 1.1 Update «Listed transaction» to expect `title`, and test the «Readable title» scenarios (bank payloads through `Transaction.title`; the own-account transfer and the imported note through `GET /api/transactions`), then add `remittance_title` to the ACL, `Transaction.title(own_ibans)` and `title` in `TransactionView` and `TransactionOut`; verify the transactions tests pass

## 2. Verification

- [ ] 2.1 Regenerate `openapi.json`; ruff, mypy, import-linter, full suite with coverage ≥ 97, spec-coverage meta-test; `docker compose up -d --build` and check the titles of stored transactions; open the PR and verify CI

## Workflow follow-up

- Archive with spec sync. Frontend change: label rows with `title`, keep `description` as detail, and show the full
  text of every truncated text on hover.
