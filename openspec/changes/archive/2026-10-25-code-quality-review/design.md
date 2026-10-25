# Design

## Context

See proposal.md. Findings from a grep-driven review of `app/`, `tests/` and `migrations/`: 4 `assert`, 7 `cast()`,
15 `type: ignore` (all in tests), 9 `noqa: E402` (conftest), 3 `except Exception`, no sleeps or mocks of internals in
tests (only `getpass`/`qrcode` monkeypatching in the CLI test).

## Goals / Non-Goals

**Goals:** fix the undated-transaction defect; no `assert`, unchecked `cast()` or `type: ignore` left without a
reason; keep every characterization test green.

**Non-Goals:** behavior changes beyond the undated transaction; block 2 fixes.

## Decisions

### Undated transactions
`normalize()` raises a domain `UndatedTransaction` when no date is present. `Ingest` catches it per payload, logs a
warning with the transaction's external reference if any, and continues; the count of new transactions excludes it.
Reprocessing cannot meet it (only stored, dated payloads are reprocessed).

### Ids of persisted entities
The four asserts sit where a just-saved or loaded entity's `id` is used. A small helper per context
(`saved_id(entity)`) raises `UnsavedEntity` with the entity type, so a broken repository fails loudly and mypy still
narrows the type.

### Parsing stored literals
`parse_literal(value, Literal[...])` in `app/shared` checks the value against `get_args()` and raises `ValueError`
naming the type; repositories use it for kind, role, status and category kind. `cast()` remains only in the event
bus (`Callable[[Any], None]`, a typing limitation of heterogeneous handler maps), with a comment.

### Test helpers
`tests/helpers.stored(db, Model, id)` expires the session, loads the row and fails with a clear message if missing.
The reprocessing test that corrupts `amount` writes a `Decimal`; the reconnection test builds `Account` with explicit
keyword arguments.

### Kept as is
- `except Exception` in `scheduled_sync`, `InMemoryEventBus.publish` and the first sync after the callback: process
  boundaries that must not take the app or the request down; each logs the exception.
- `conftest.py` starting Postgres and setting `DATABASE_URL` before importing `app` (the engine is created at import);
  the `noqa: E402` lines are the cost of that, explained in its docstring.
- Characterization tests reading ORM rows to assert persisted state: intended since `specs-base`.

## Risks / Trade-offs

- [`parse_literal` can now raise on legacy data] → The database only contains values the app wrote; a failure would
  reveal corruption instead of hiding it.

## Migration Plan

Code-only; rebuild the image. Rollback: revert the PR.
