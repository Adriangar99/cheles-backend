# Proposal

## Why

A review of the backend for bad practices (unchecked casts, `assert` used for control flow, `type: ignore`, broad
`except`, odd tests) found one real defect and a few weak spots:

- **A transaction without any date breaks the sync.** `normalize()` does `date.fromisoformat(cast(str, ...))`; when
  the bank sends no `booking_date`, `value_date` or `transaction_date`, the `cast` hides a `None` and the sync of that
  account fails with a `TypeError` (500 on a manual sync, the remaining accounts are not read, and the error is not
  even recorded as the connection's `last_error`).
- **`assert` in production code** (4 places) guards "persisted entities have an id"; asserts vanish under `python -O`
  and turn a broken invariant into a confusing `AttributeError` later.
- **Unchecked `cast()` of stored strings to `Literal` types** (kind, role, status, category kind): a bad value in the
  database would flow through the domain silently.
- **`type: ignore` in tests** (15): mostly `db.get(...).field` on an optional result, plus a deliberately wrong
  assignment and a `**dict` call that defeats the dataclass signature.

## What Changes

- Transactions without any date are skipped with a warning; the rest of the batch is stored (spec MODIFIED).
- `assert` in `app/` replaced by explicit errors: an `UnsavedEntity` (or equivalent per context) raised when a use case
  needs the id of an entity that has none.
- Stored literals parsed with checked helpers (`parse_kind`, `parse_role`, …) that raise on unknown values, instead of
  `cast()`.
- Tests: a `stored(db, Model, id)` helper that refreshes and fails clearly when the row is missing replaces the
  `type: ignore[union-attr]`; the remaining two ignores are rewritten with typed values.
- Reviewed and kept (documented in design): the three broad `except Exception` (scheduled sync, event handlers and the
  first sync after connecting are deliberate "log and carry on" boundaries); the conftest that starts Postgres at import
  time (the engine is built at import); tests that assert stored rows (characterization of persisted state).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `transactions/transaction-ingestion`: undated transactions are skipped instead of breaking the sync.

## Impact

- **Bounded contexts affected**: transactions (payload normalization, ingestion, repository), banking and
  categorization (repositories, use cases).
- **API**: unchanged. **Persistence**: unchanged.
- **Security surface**: unchanged.

### Out of scope

- The behavior fixes of block 2 (login timing, pending authorizations, statistics…).
