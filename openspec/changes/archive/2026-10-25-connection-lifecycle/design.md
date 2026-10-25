# Design

## Context

See proposal.md. `BankingProvider` already declares `delete_session` (the Enable Banking client implements it; nothing
calls it). `pending_auths.created_at` exists in the table but not in the `PendingAuthorization` domain object.
`SyncConnection` checks `consent_expired()` but not `status`. Accounts already support `connection_id = None`
(`detached_accounts`), and reconnection re-links by identification hash, then IBAN.

## Goals / Non-Goals

**Goals:** a removable connection; no provider calls for non-active connections; no stale pending authorizations;
the connection's country in the API.

**Non-Goals:** deleting stored transactions; UI.

## Decisions

### Removing = revoke + detach
`RemoveConnection(connection_id)`: load (404 if missing), `provider.delete_session(session_id)` inside
`try/except ProviderError | ProviderNotConfigured` (logged), `connection.revoke()` (status `revoked`), and for every
account of the connection `account.detach()` (`connection_id = None`, `eb_uid = None`), then commit. Keeping the row
preserves history and lets a later reconnection find the accounts by identification hash. The repository's listing
excludes `revoked`.

### Manual sync of non-active connections
`SyncConnection` returns `SyncResult(0, status, last_error)` before any provider call when `status != "active"`; the
existing consent-date check stays for active connections.

### Cleanup of pending authorizations
`PendingAuthorization` gains `created_at`; the repository gets `delete_started_before(cutoff)`. `StartAuthorization`
calls it with `clock.now() - 1 hour` before adding the new one.

### Country
`ConnectionOut.country` from `aspsp_country`.

## Risks / Trade-offs

- [Session deletion fails at the bank] → The consent stays alive at Enable Banking until it expires; the local
  connection is still removed, which is what the user asked for. Logged.

## Migration Plan

Code-only (no schema change); regenerate `openapi.json`. Rollback: revert the PR.
