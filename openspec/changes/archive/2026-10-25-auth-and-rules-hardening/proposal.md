# Proposal

## Why

Two observations recorded in `specs-base`, picked for block 2 of the roadmap:

- **Login timing reveals whether a username exists.** The check short-circuits: an unknown user skips the password
  hash (Argon2, the slow part) and a wrong password skips the TOTP check, so response time tells an attacker which
  step failed, despite the identical 401.
- **An empty rule pattern matches everything.** `POST /api/rules` accepts a pattern that is empty after trimming; at
  priority 10 it overrides every default rule and recategorizes the whole history.

## What Changes

- Login always verifies one password hash (against a fixed dummy hash when the user does not exist) and one TOTP code
  (against a dummy secret), and combines the results without short-circuiting.
- Creating a rule with a pattern that is empty once trimmed answers 400 «El patrón no puede estar vacío»; nothing is
  stored or reprocessed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `identity/user-authentication`: login does the same work for every failure.
- `categorization/transaction-categorization`: empty rule patterns are rejected.

## Impact

- **Bounded contexts affected**: identity (login use case), categorization (rule creation), composition edge
  (`POST /api/rules` error mapping).
- **API**: new 400 for empty patterns; no contract change otherwise.
- **Security surface**: reduced (username enumeration by timing).

### Out of scope

- The rest of block 2 (`connection-lifecycle`, `stats-accuracy`, frontend fixes).
