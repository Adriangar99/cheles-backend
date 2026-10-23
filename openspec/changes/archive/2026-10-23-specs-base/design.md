# Design

## Context

The backend is a flat FastAPI package (`app/`, about 1,100 lines) with no tests: routes, serialization and business
rules live together in `app/main.py`, and domain logic depends on SQLAlchemy sessions. See proposal.md for why we
document it before restructuring it. The specs in this change were derived by reading every module (`main.py`,
`sync.py`, `categorize.py`, `stats.py`, `security.py`, `enablebanking.py`, `cli.py`, `models.py`, `config.py`).

## Goals / Non-Goals

**Goals:**
- A behavioral contract that is precise enough to write characterization tests against the HTTP API and the CLI
  without reading the code again.
- A capability layout that already matches the target bounded contexts, so later changes only add deltas.

**Non-Goals:**
- Judging or fixing behavior. Where current behavior looks wrong, the spec still describes it; doubtful cases are
  listed below as observations.
- Placing entities, value objects, ports or adapters: this change introduces none. No Alembic migration is needed.

## Decisions

### Capabilities grouped by bounded context path
Capabilities are named `<context>/<capability>` (e.g. `banking/bank-sync`), mirroring the planned
`app/<context>/` packages. Alternative considered: a flat list (`bank-sync`, `stats`…). Rejected because ownership of
each requirement by a context would be implicit, and the migration changes would have to rediscover it.

### Cross-context behavior is owned by the context that reacts
Reprocessing is triggered from banking (IBAN change) and categorization (new rule), but it recomputes transactions, so
it is specified in `transactions/reprocessing`, and the triggering capabilities only state that a reprocess happens.
These triggers are the future domain events (e.g. `AccountIbanChanged`, `CategorizationRuleCreated`), but naming
events is left to the migration changes.

### Describe the HTTP contract, not the internals
Specs reference endpoints, payload fields, status codes and stored observable state (e.g. "only the SHA-256 of the
token is stored"), never module or function names. That way the characterization tests survive the restructuring
unchanged.

### Known defect specified as current behavior
The manual ⇄ mark being recomputed is written as a requirement labeled "known defect", with scenarios that will turn
into characterization tests. The fix change will MODIFY that requirement and flip those tests, which makes the
behavior change explicit in the spec history.

### User-facing literals quoted verbatim
Error details and UI-relevant strings (e.g. «Datos incorrectos», «Sin categoría») are kept in Spanish as they appear
today, since they are part of the observable contract. Moving to error codes plus frontend translation is a possible
future change, not part of this one.

## Observations (not specified as requirements, not fixed)

Candidates for future changes found while reading the code:

- **Login is not constant-time**: despite the code comment, checks short-circuit (unknown user skips password hashing;
  wrong password skips TOTP), so response time can reveal whether the username exists.
- **Empty rule pattern**: `POST /api/rules` accepts a pattern that is empty after trimming; it matches every
  transaction and, at priority 10, overrides every default rule.
- **Pending authorizations are never cleaned up** when the callback fails or the user abandons the bank flow.
- **Manual sync ignores status**: `POST /api/banks/{id}/sync` attempts a sync on an `expired` connection as long as
  `valid_until` is in the future.
- **Balances mix currencies** in `balances.total`, and stats sum amounts regardless of currency.
- **Stats include pending transactions**, which are later deleted and replaced when booked.
- **Edits on pending transactions are lost** because they are deleted on every sync.
- **`revoked` status** exists in the model but nothing sets it, and there is no endpoint to delete a connection.
- **Login throttle is in-memory**, so it resets on restart (acceptable for a single local user, but worth stating).
- **Full reprocess on every rule/IBAN change** loads every transaction in one request; fine at current volume.
- **Schema created with `create_all`** at startup, with no migrations; categories are seeded only on an empty table.

## Risks / Trade-offs

- [The spec describes the code as read, and could misdescribe a subtle path] → The characterization tests in the next
  change are written from these scenarios; any mismatch found there is fixed in the spec before archiving that change.
- [Specifying defects as requirements may make them look intended] → They are explicitly labeled "known defect" or
  listed as observations, and each has a planned follow-up.
- [Spanish literals in English specs] → Quoted with «» so they read as data, not prose.
