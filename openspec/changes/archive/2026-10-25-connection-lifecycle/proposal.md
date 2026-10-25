# Proposal

## Why

Observations recorded in `specs-base` about the life of a bank connection, picked for block 2:

- **Pending authorizations are never cleaned up** when the bank flow is abandoned or fails.
- **A manual sync ignores the status**: `POST /api/banks/{id}/sync` reads an `expired` connection as long as its
  `valid_until` is in the future, calling Enable Banking with a consent the bank already rejected.
- **`revoked` exists but nothing sets it**, and there is no way to remove a connection.
- **The country of a connection is not exposed**, so the web app reconnects every bank with «ES».

## What Changes

- `DELETE /api/banks/{id}` removes a connection: closes the Enable Banking session (errors logged, not blocking), marks
  it `revoked` and detaches its accounts, which keep transactions, role, alias and IBAN. Revoked connections are not
  listed; reconnecting the bank re-links the accounts as today.
- A manual sync of a connection that is not `active` returns its status without calling Enable Banking.
- Starting an authorization deletes pending authorizations older than one hour.
- `GET /api/banks` exposes each connection's `country`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `banking/bank-sync`: manual sync skips connections that are not active.
- `banking/bank-connection`: removing a connection; cleanup of abandoned authorizations.
- `banking/accounts`: revoked connections are not listed; `country` per connection.

## Impact

- **Bounded contexts affected**: banking (domain, use cases, ports, repositories, HTTP).
- **API**: new `DELETE /api/banks/{id}` (204/404); new `country` field; `openapi.json` regenerated.
- **Persistence**: none (the `revoked` status, `aspsp_country` and `created_at` already exist).
- **Security surface**: removing a connection also closes the bank session at Enable Banking.

### Out of scope

- The frontend «quitar» button and reconnect country (frontend change `fix-banks-and-errors`).
- `stats-accuracy`.
