# Tasks

TDD: write the scenario test first and see it fail for the right reason. Commit before any mutation check.

## 1. Login

- [ ] 1.1 Test «Same work for every failure» with spies on the hasher and TOTP ports, then make `Login` always verify a hash and a code (dummy hash and secret for unknown users); verify the identity tests pass and mutation-check the non-short-circuit evaluation

## 2. Rules

- [ ] 2.1 Test «Empty pattern», then raise `EmptyRulePattern` in `CreateRule` and map it to 400 in `POST /api/rules`; verify the categorization tests pass

## 3. Verification

- [ ] 3.1 ruff, mypy, import-linter, full suite with coverage ≥ 97 and the spec-coverage meta-test; open the PR and verify CI

## Workflow follow-up

- Archive with spec sync (`/opsx:archive`). Next: `connection-lifecycle`.
