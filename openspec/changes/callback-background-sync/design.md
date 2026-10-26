# Design

## Context

See proposal.md. `CompleteAuthorization` commits the connection and its accounts, then calls `SyncConnection` and
catches any exception to log «Falló la primera sincronización». `bank_callback` turns its boolean into the redirect.
`SyncConnection` opens its own unit of work and commits per account, so it does not depend on the callback's.

## Goals / Non-Goals

**Goals:** the callback answers in the time it takes to create the session and store the connection; the first sync
still happens, right after.

**Non-Goals:** a job queue or retries (the scheduled sync already picks up any connection whose first sync was lost,
e.g. by a restart); asynchronous manual syncs.

## Decisions

### `CompleteAuthorization` stops syncing
It returns the id of the new connection, or `None` when the bank reported an error, data is missing or the session
fails (it returned `False` in those cases). It no longer holds `SyncConnection`.

### `FirstSync` use case
A banking use case wrapping `SyncConnection`: it syncs the connection and logs any exception as «Falló la primera
sincronización» without raising, since nobody is waiting for it. It lives in the application layer, next to
`SyncConnection`, so the HTTP adapter only schedules it.

### Scheduling with FastAPI `BackgroundTasks`
`bank_callback` takes `BackgroundTasks` and, when a connection was created, adds `services.first_sync(connection_id)`.
Starlette runs it after the response has been sent, in the threadpool (the use cases are synchronous), so the browser
gets the redirect immediately. The banking unit of work is per request and opens a new SQLAlchemy session on every
`with`, so using it after the response is safe. The APScheduler was discarded: a one-off job per connection adds state
to the scheduler for no gain over `BackgroundTasks`.

## Risks / Trade-offs

- [The process stops during the first sync] → Transactions are committed per account, so nothing is half-written; the
  next scheduled sync reads the rest.
- [«bancos» loads before the sync ends] → It shows the connection without balances or `last_synced_at`; the web app
  can show it as syncing (out of scope).

## Migration Plan

Code-only, no Alembic migration and no API contract change. Rollback: revert the PR.
