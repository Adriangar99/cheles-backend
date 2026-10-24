# Proposal

## Why

Two defects recorded while specifying the backend:

- **The manual ⇄ mark is lost.** Marking a transaction as a transfer between own accounts is not stored as manual: the
  next sync that includes it, or any reprocess (after a rule, an IBAN change or «volver a automática»), recomputes the
  kind from the counterparty IBAN and turns it back into a normal expense or income. The current specs describe this as
  a known defect.
- **A missing Enable Banking configuration is a 500.** Without `EB_APPLICATION_ID` (or with an unreadable private key)
  listing banks, connecting one or syncing fails with an unhandled error, so the web app can only show «Error 500».

## What Changes

- **Manual kind**: a transaction stores whether its kind was set by hand (`kind_manual`). `PATCH
  /api/transactions/{id}` with `kind` sets a manual kind when it differs from the one derived from the counterparty
  IBAN, and clears the manual mark when it matches it (so «quitar» on a manually marked transfer returns it to the
  automatic kind). Sync and reprocessing keep a manual kind. The automatic category follows the resulting kind: none for
  a transfer, the suggested one for a normal transaction, unless the category is manual.
- `kind_manual` is exposed with every transaction, next to `category_manual`.
- **Missing provider configuration**: listing banks, starting an authorization and syncing (one or every connection)
  answer **503**
  with detail «Enable Banking no está configurado» when the application id is missing or the private key cannot be
  read; the authorization callback redirects to `/bancos?error=1`. Scheduled syncs keep logging the failure.
- Database migration adding the `kind_manual` column (false for existing rows).
- `openapi.json` regenerated (new `kind_manual` field).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `transactions/transaction-management`: transaction representation gains `kind_manual`; the known-defect requirement
  «Manual transfer mark (⇄)» is removed and replaced by «Stored manual kind (⇄)».
- `transactions/reprocessing`: reprocessing keeps a manual kind.
- `transactions/transaction-ingestion`: transfer detection does not override a manual kind.
- `banking/bank-connection`: a missing Enable Banking configuration answers 503 with a readable detail.

## Impact

- **Bounded contexts affected**: transactions (aggregate, edit use case, persistence, HTTP model), banking (provider
  adapter, HTTP error mapping, callback).
- **Persistence**: new Alembic migration `0002_kind_manual`. There is no production data yet (no user has been
  created), so no backfill of earlier manual marks is needed.
- **API**: additive field `kind_manual`; new 503 response. The frontend picks the contract up with `pnpm api:sync` in
  its own change.
- **Security surface**: unchanged.

### Out of scope

- Other observations recorded in `specs-base` (constant-time login, empty rule patterns, pending authorizations…).
- Frontend changes (separate change in cheles-frontend).
