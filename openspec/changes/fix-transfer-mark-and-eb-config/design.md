# Design

## Context

See proposal.md. `Transaction.derive(own_ibans, suggester)` recomputes `kind` from the counterparty IBAN on every
ingestion and reprocess, and only keeps a manual category. `EditTransaction` sets `kind` directly without recomputing
the category and without recording that it was manual. The Enable Banking client raises `RuntimeError` when
`EB_APPLICATION_ID` is empty and lets `open()` fail when the key file is missing; neither is a `ProviderError`, so the
HTTP layer answers 500.

The characterization tests «The mark is lost on reprocess (known defect)» and «The mark is lost on sync (known
defect)» encode the old behavior; this change flips them with the MODIFIED requirement, as planned in `specs-base`.

## Goals / Non-Goals

**Goals:** a stored, respected manual kind with clear semantics for «quitar»; a readable 503 for a missing provider
configuration.

**Non-Goals:** other recorded observations; cleaning up pending authorizations; frontend changes.

## Decisions

### Manual kind as an override of the derived kind
`Transaction` gains `kind_manual: bool`. `derive()` computes the automatic kind and applies it only when
`kind_manual` is false; the automatic category then follows the resulting kind (none for a transfer, the suggestion
otherwise) unless the category is manual. A new domain method `set_kind(kind, own_ibans, suggester)`:
- stores `kind_manual = kind != automatic_kind` and `kind = kind`,
- re-derives the category for the new kind.

So «quitar» on a manually marked transfer returns to the automatic kind (the user's choice), and on a transfer detected
by IBAN it stores a manual `normal`, so the button never silently does nothing.

### EditTransaction gets the suggestions port
Re-deriving the category needs the own IBANs (already available through `OwnAccounts`) and the category suggester, so
`EditTransaction` receives `CategorySuggestions` from the composition root, like `Ingest` and `ReprocessAll`.

### Persistence and migration
`TransactionRow.kind_manual` (`Boolean`, not null, server default false) mapped both ways in the repository.
Alembic revision `0002_kind_manual` adds the column; downgrade drops it. No backfill: there is no production data.

### API
`TransactionOut` gains `kind_manual: bool`; `openapi.json` is regenerated and the drift test keeps it in sync. The
request model is unchanged (`kind` already exists).

### Provider not configured
- `banking/domain/errors.py`: `ProviderNotConfigured(Exception)`, distinct from `ProviderError` so a sync does not record
  it as the connection's `last_error` or touch `last_synced_at`.
- `EnableBankingClient._jwt()` raises it when the application id is empty or the key file cannot be read (`OSError`).
  It is raised before any request, so nothing has been ingested when it propagates and the sync's unit of work is
  rolled back.
- HTTP: available banks, connect, sync one and sync all map it to `HTTPException(503, "Enable Banking no está configurado")`.
- Callback: `CompleteAuthorization` treats it like a `ProviderError` (returns false → `/bancos?error=1`).
- Scheduled sync: unchanged; the generic handler in `app/main.py` already logs it.

### Tests
- Transactions: the two known-defect characterization tests become «The mark survives a reprocess/sync»; new tests per
  new scenario (remove a manual mark, mark a detected transfer as normal, automatic kind listed, manual kind on
  reprocess and ingestion). Domain unit tests for `set_kind` only where API tests do not reach.
- Banking: one test per new scenario with a client built from settings without application id / with a missing key
  path; the client is exercised directly for the key-file case.
- Migration: `alembic upgrade head` on a fresh database and on a 0001 database in the existing migration test setup.

## Risks / Trade-offs

- [`set_kind` on a detected transfer stores a manual `normal`] → Deliberate: otherwise «quitar» would do nothing for
  those rows; specified in «Mark a detected transfer as normal».
- [Pending authorization stored before the 503 on connect] → Same as today for provider errors; cleaning them up is a
  recorded observation, out of scope.

## Migration Plan

Deploy runs `python -m app.cli migrate` on container start, which applies `0002_kind_manual`. Rollback: revert the PR
and `alembic downgrade 0001_baseline`.
