# Tasks

TDD: write the scenario test first and see it fail; refactors keep every test green. Commit before any mutation check.

## 1. Undated transactions

- [x] 1.1 Test «No date at all» (a sync with one dated and one undated transaction), then raise `UndatedTransaction` in `normalize()` and skip it in `Ingest` with a warning; verify the ingestion and sync tests pass and mutation-check the skip

## 2. Invariants and literals

- [ ] 2.1 Replace the four production `assert` with `saved_id()` raising `UnsavedEntity`, and the repository `cast()` of stored literals with `parse_literal()`; verify ruff, mypy, import-linter and the full suite pass

## 3. Tests

- [ ] 3.1 Add `tests/helpers.stored()` and remove every `type: ignore` from the tests (typed values for the two non-optional cases); verify mypy and the full suite pass with coverage ≥ 97, and CI on the PR

## Workflow follow-up

- Archive the change with spec sync (`/opsx:archive`).
- Next: the frontend `code-quality-review`, then block 2 (fixes).
