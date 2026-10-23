# Proposal

## Why

Banking is the last operational part of the app still in legacy modules: connections, pending authorizations and
accounts in `app/models.py`, the sync in `app/sync.py`, the Enable Banking client in `app/enablebanking.py`, and the
bank and account routes in `app/main.py`. Transactions currently reads own accounts through the transitional
`app/legacy_bridge.py`. Migrating banking removes those modules and the bridge, and brings the first cross-context
reaction that does not need to answer its caller, which is the agreed trigger for the event bus.

## What Changes

- **Event bus** in the shared kernel (`app/shared/events.py`): an in-memory, synchronous bus; use cases publish
  events only after their unit of work commits, and each handler runs in its own transaction. A failing handler is
  logged and does not undo the publisher's committed change.
- **`app/banking/`** bounded context:
  - domain: `BankConnection`, `Account` (role, alias, `Iban`, balance as `Money`), `PendingAuthorization`, and the
    rules now spread over legacy code: consent expiry, Enable Banking error → expired, balance type preference, sync
    window, reconnection matching (identification hash, then IBAN); event `AccountIbanChanged`;
  - application: ports (repositories + unit of work, `BankingProvider` for Enable Banking, `TransactionsGateway`
    for the latest booked date and ingestion, event publisher, clock, state generator) and use cases: list
    connections and detached accounts, list available banks, start authorization, complete authorization (with the
    first sync), sync one connection, sync all active connections, update an account, and own-accounts queries for
    other contexts;
  - infrastructure: ORM rows on the same tables (no migration), repositories, the Enable Banking HTTP client as the
    `BankingProvider` adapter, and the router for `/api/banks*`, `/api/sync` and `/api/accounts/{id}`.
- **Composition root**: wires `AccountIbanChanged` → transactions reprocess; serves transactions' `OwnAccounts` from
  `app.banking.public` and banking's `TransactionsGateway` from `app.transactions.public`; the scheduled sync calls
  banking.
- **Removed**: `app/models.py`, `app/sync.py`, `app/enablebanking.py`, `app/legacy_bridge.py`, and the bank/account
  routes in `app/main.py`.
- **Stats**: its transitional import-linter exception now also covers banking's ORM rows (read-only), until stats is
  migrated.
- **Tests**: the fake Enable Banking is installed through the container instead of monkeypatching modules.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Pure refactor (`skip_specs: true`): `banking/*`, `transactions/*` and `stats/financial-summary` keep every
requirement and scenario.

## Impact

- **Bounded contexts**: banking (migrated). Banking ↔ transactions only through ports adapted at the composition root
  and one event; legacy code left: `app/main.py` (stats routes, rules orchestration, lifespan/scheduler), `app/stats.py`
  and `app/cli.py`.
- **Cross-context events**: `AccountIbanChanged(account_id)` published by banking after an IBAN update commits;
  handled by the composition root, which runs transactions' reprocess.
- **Security surface**: unchanged; every banking route keeps requiring a session; Enable Banking credentials and the
  private key path are read exactly as before.
- **Database**: same tables; no migration.
- **Behavior**: identical on success paths. On a failing reprocess after an IBAN change the IBAN stays saved and the
  error is logged (previously the request failed after the IBAN was already committed).

### Out of scope

- Migrating stats (next change) and removing `bootstrap.current()` from the remaining legacy routes.
- Any fix to recorded observations (e.g. pending authorizations never cleaned up, manual sync of expired connections).
