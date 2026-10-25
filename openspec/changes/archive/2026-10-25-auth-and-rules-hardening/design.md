# Design

## Context

See proposal.md. `Login` evaluates `user is None or not (hasher.verify(...) and totp.verify(...))`; `CreateRule`
strips the pattern and stores it whatever its length.

## Goals / Non-Goals

**Goals:** equal work on every login failure; no empty rule patterns.

**Non-Goals:** measuring wall-clock timing in tests (flaky); rate limiting changes.

## Decisions

### Equal work
- A module-level dummy Argon2 hash (computed once at import with the real hasher) and a fixed dummy base32 secret.
- `Login`: `password_ok = hasher.verify(user.password_hash if user else DUMMY_HASH, password)`; `code_ok =
  totp.verify(user.totp_secret if user else DUMMY_SECRET, code)`; success only if `user and password_ok and code_ok`.
  Both checks always run.
- Test through spies on the container's `hasher` and `totp` ports, counting calls per attempt; wall-clock assertions
  are avoided.

### Empty pattern
`CreateRule` raises a domain `EmptyRulePattern` before touching the database; `POST /api/rules` maps it to 400
«El patrón no puede estar vacío» and skips the reprocess.

## Risks / Trade-offs

- [Every failed login now costs one Argon2 hash] → Intended; the per-IP limit (5 attempts) already bounds it.

## Migration Plan

Code-only. Rollback: revert the PR.
