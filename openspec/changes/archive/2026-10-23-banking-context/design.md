# Design

## Context

See proposal.md. Legacy code being migrated:

- `app/models.py`: `PendingAuth`, `BankConnection` (with `accounts` relationship), `Account` (with `connection`).
- `app/enablebanking.py`: JWT-signed HTTP client (`list_aspsps`, `start_auth`, `create_session`, `get_balances`,
  `get_transactions` with continuation keys) and `EnableBankingError(status_code, body)`.
- `app/sync.py`: `normalize_iban`, balance preference (`ITAV, CLAV, XPCD, ITBD, CLBD`, else first, else none),
  window (latest booked − 10 days or `initial_history_days`), `sync_account` (both Enable Banking calls before
  writing), `sync_connection` (expired consent → `expired` without calls; Enable Banking error → `last_error`
  truncated to 1024, `expired` on 401/403; `last_synced_at` always), `sync_all` (active connections only).
- `app/main.py`: `/api/banks` (connections ordered by id + detached accounts), `/api/banks/available`,
  `/api/banks/connect`, `/api/banks/callback` (reconnection matching, first sync, 303 redirects),
  `/api/banks/{id}/sync`, `/api/sync`, `PATCH /api/accounts/{id}` (role, alias, IBAN → reprocess), `scheduled_sync`.
- Tests install `FakeEnableBanking` by monkeypatching `app.main.EnableBankingClient` and `app.sync.EnableBankingClient`.

## Goals / Non-Goals

**Goals:** identical HTTP behavior and stored data; no legacy module except `main.py`, `stats.py`, `cli.py`; the event
bus used by a real flow.

**Non-Goals:** migrating stats; changing Enable Banking authentication; behavior fixes.

## Decisions

### Event bus (shared kernel)
`app/shared/events.py`: `Event` (base frozen dataclass), `EventPublisher` (Protocol with `publish(event)`) and
`InMemoryEventBus` (`subscribe(event_type, handler)`, `publish` calls every handler synchronously, logging and
swallowing handler exceptions). Use cases receive an `EventPublisher` and call `publish` **after** `uow.commit()`,
which is how «dispatch after commit» is guaranteed without a unit of work that collects events (kept simple until a
use case publishes several events). Handlers open their own unit of work. The bus lives in the kernel because the
mechanism means the same to every context; the event types belong to their publisher (`AccountIbanChanged` in
`app.banking.domain.events`, exported by `app.banking.public`). Subscriptions are wired in `app/bootstrap.py`, so
transactions does not know banking's events.

### Banking layout

```
app/banking/
  domain/
    connection.py     # BankConnection (status, consent expiry, record_sync_error), PendingAuthorization
    account.py        # Account, AccountRole, Iban (VO), apply_update(role, alias, iban) -> iban_changed
    sync_policy.py    # sync window, balance preference
    reconnection.py   # match an incoming account against known ones (identification hash, then IBAN)
    events.py         # AccountIbanChanged
    errors.py         # ConnectionNotFound, AccountNotFound, ProviderError(status_code, body)
  application/
    ports.py          # repositories + UnitOfWork, BankingProvider, TransactionsGateway, Clock, StateGenerator
    use_cases.py      # ListConnections, ListAvailableBanks, StartAuthorization, CompleteAuthorization,
                      #   SyncConnection, SyncAll, UpdateAccount, OwnAccountIbans, AccountDisplayNames
  infrastructure/
    orm.py            # BankConnectionRow, AccountRow, PendingAuthRow (same tables)
    repositories.py
    enable_banking.py # the JWT HTTP client (moved) implementing BankingProvider; raises ProviderError
    http.py           # routes, placeholder dependency
  public.py           # BankingServices, AccountIbanChanged, OwnAccountsQuery types for other contexts
```

### Value objects
- `Iban` (banking): an own account's IBAN, normalized (no spaces, uppercase). It identifies accounts on reconnection.
  It is deliberately separate from transactions' `CounterpartyIban`.
- Balance is a kernel `Money`; `AccountRole` stays a banking literal (`main | savings | excluded`). Stats keeps
  reading the role column directly through its exception until it gets its own read model.

### Enable Banking adapter and errors
The HTTP client moves unchanged into `infrastructure/enable_banking.py` and raises the domain `ProviderError`
(same `status_code`/`body`, same message format `Enable Banking {status}: {body}`) so the application layer does not
import infrastructure. The `Container` holds a `banking_provider` field (default: the real client); tests replace it
with `FakeEnableBanking`, which no longer needs module monkeypatching.

### Sync transactions
`SyncConnection` uses one banking unit of work per connection: for each linked account it asks
`TransactionsGateway.latest_booked_date`, calls `fetch_transactions` and `fetch_balances` (both before any write),
calls `TransactionsGateway.ingest`, sets the balance and commits; on `ProviderError` it rolls back the current
account, records the error (`expired` on 401/403) and commits the connection state. Same observable semantics as
`app/sync.py`.

### Authorization callback
`CompleteAuthorization(code, state, error)` returns whether it connected. It keeps the order: unknown/failed →
`False` without writes; otherwise create the connection with the session's `valid_until`, match accounts
(`reconnection.py`), delete the pending authorization, commit, then run `SyncConnection` and log
«Falló la primera sincronización» on any exception. The router maps the result to the 303 redirects.

### Cross-context wiring at the composition root
- Transactions' `OwnAccounts` → `banking.own_account_ibans()` / `banking.account_display_names(ids)`.
- Banking's `TransactionsGateway` → `transactions.latest_booked_date` / `transactions.ingest`.
- `bus.subscribe(AccountIbanChanged, lambda _: container.transactions().reprocess_all())`.
- `app/main.py` lifespan schedules `container.banking().sync_all` and logs the count as before.

### Contracts
Banking joins every per-context contract; the legacy module list shrinks to `app.main`, `app.cli`, `app.stats`; the
stats exception adds `app.stats -> app.banking.infrastructure.orm`; `app.legacy_bridge` disappears from the lists.

### Tests
Characterization tests keep their expected values; changes are imports (banking ORM rows), the fake installed through
the container, the pagination test pointing at the moved client, and the scheduled-sync failure stub patching the
container instead of `app.main.sync_all`. New unit tests only for `reconnection.py` (hash first, then IBAN, keeps an
existing IBAN when the bank sends none) and the event bus (handlers run after publish; a failing handler is logged
and does not stop the others), the two pieces of logic that are new or restructured.

## Risks / Trade-offs

- [Synchronous in-memory bus] → Simple and enough for one process; if a handler is slow the request waits, as today.
- [Handler failures are swallowed] → Logged; the reprocess endpoint stays available to recover manually.
- [Stats exception grows] → Still explicit and read-only; removed by the next change.

## Migration Plan

Refactor only; rebuild the image. No data or schema change.
