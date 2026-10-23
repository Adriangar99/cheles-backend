# Proposal

## Why

`openspec/specs/` is empty: the backend's behavior only exists in code, with no tests and no written requirements.
Before migrating to a hexagonal architecture organized by bounded contexts we need an explicit contract of the
current behavior, to drive characterization tests and to review every step of the refactor.

## What Changes

- Document the **current** backend behavior as-is, as specs organized by bounded context (`identity`, `banking`,
  `transactions`, `categorization`, `stats`).
- Write scenarios so that each one maps one-to-one to a characterization test in the next change.
- Also document the known defect: the manual transfer mark (⇄) is lost on sync or reprocess. It will be fixed in a
  separate change (`fix-manual-transfer-mark`) as a delta of `transactions/transaction-management`.
- Record other oddities found while reading the code as observations in `design.md`, without specifying or fixing them.
- Translate `README.md` to English, in line with the project's language convention (code and docs in English, UI in
  Spanish).
- No changes to code, API, database schema or configuration.

## Capabilities

### New Capabilities

- `identity/user-authentication`: CLI creation of the single user, login with password + TOTP, HttpOnly cookie
  session, logout, current user and per-IP login attempt limit.
- `banking/bank-connection`: list of available banks, starting authorization with Enable Banking, callback, and
  re-linking already known accounts on reconnection.
- `banking/bank-sync`: scheduled and manual sync, incremental window, pending transaction replacement, balances,
  errors and consent expiry.
- `banking/accounts`: list of connections and accounts, account role (main / savings / excluded), alias and manual IBAN.
- `transactions/transaction-ingestion`: normalization of a transaction from the Enable Banking `raw` payload, external
  id, and detection of transfers between own accounts by IBAN.
- `transactions/transaction-management`: filtered listing and manual edits (category, kind, note), including the
  known ⇄ defect.
- `transactions/reprocessing`: recomputing every transaction from `raw` while respecting manual edits.
- `categorization/transaction-categorization`: default categories, pattern rules with priority, fallback categories,
  received Bizum and user-created rules.
- `stats/financial-summary`: monthly summary (income, expenses, net, savings, spending by category), monthly history
  and balances by role.

### Modified Capabilities

None (there are no existing specs).

## Impact

- Only files under `openspec/` and `README.md` change. Nothing changes in `app/`, `docker-compose.yml` or the database.
- **Bounded contexts**: all five, documentation only. Each capability's path anticipates the target structure.
- **Cross-context events**: none added or changed. There are no events today; the implicit dependencies between
  contexts (e.g. changing an IBAN reprocesses transactions) are captured in the scenarios.
- **Security**: the security surface does not change. The current behavior of authentication, sessions and throttling
  becomes a verifiable contract.

### Out of scope

- Fixing any behavior, including the ⇄ mark.
- Tests, tooling, migrations and code restructuring (next changes).
- Translating code identifiers, comments or API error messages (done context by context during the migration).
- Deployment and Docker networking, `/api/health`, and Enable Banking dashboard setup.
- The frontend (it has its own `specs-base` in `cheles-frontend`).
