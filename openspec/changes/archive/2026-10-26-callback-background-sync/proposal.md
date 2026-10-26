# Proposal

## Why

`GET /api/banks/callback` creates the connection, links its accounts and then runs the first sync (up to
`INITIAL_HISTORY_DAYS`, 730 days) **before** answering (issue #30). With a bank that returns a long history this takes
minutes, the web app's `/api` proxy gives up (`socket hang up`) and the browser shows a bare «Internal Server Error»,
although the connection was saved and the sync finishes anyway.

## What Changes

- The callback answers 303 to `/bancos?connected=1` as soon as the connection and its accounts are committed.
- The first sync runs in the background after the response is sent. Its failures are still logged and change nothing
  else. Until it finishes, the connection is listed with `last_synced_at` null, which tells the web app it has not been
  read yet.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `banking/bank-connection`: the authorization callback no longer waits for the first sync.

## Impact

- **Bounded contexts affected**: banking (use cases, HTTP adapter, composition root).
- **Cross-context events**: none added or changed.
- **API**: same responses; only their timing changes. `openapi.json` unchanged.
- **Persistence**: none.
- **Security surface**: none.

### Out of scope

- Showing the connection as «sincronizando» in «bancos» (frontend; it can rely on `last_synced_at` being null).
- Raising the proxy timeout, which would only hide the problem.
- Making manual syncs (`POST /api/banks/{id}/sync`, `POST /api/sync`) asynchronous.
