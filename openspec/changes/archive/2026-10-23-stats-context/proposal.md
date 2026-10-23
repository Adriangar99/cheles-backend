# Proposal

## Why

Stats is the last legacy piece: `app/stats.py` aggregates other contexts' tables with SQL through a documented
import-linter exception, and it, the stats routes and the startup code in `app/main.py` still reach services through
the transitional `bootstrap.current()`. Migrating stats completes the hexagonal migration of the backend: every
context owns its data, depends only on ports, and no exception or service locator remains.

## What Changes

- **Published read models** (Open Host Service):
  - transactions publishes `ListMovements(start, end)` returning `MovementRecord(account_id, booking_date, amount,
    kind, category_id)` for a date range (or all time);
  - banking publishes `AccountSnapshots()` returning `AccountSnapshot(account_id, role, balance)`;
  - categorization's existing `CategoryLabels` is reused.
- **`app/stats/`** bounded context:
  - domain: stats' own view of the inputs (`Movement`, `AccountStanding` with «counts» and «is savings» derived from
    the role) and pure aggregation rules: counted movements, monthly summary (income, expenses, net), savings of the
    month, spending by category with the «Sin categoría» default, monthly history, balances by role;
  - application: ports (`MovementsSource`, `AccountsSource`, `CategoryLabelsSource`, `Clock`) and use cases
    `MonthlySummary` and `MonthlyHistory`;
  - infrastructure: the router for `/api/stats/summary` and `/api/stats/history`.
- **Composition root** adapts the three ports to the other contexts' public APIs.
- **Composition edge cleanup**: `app/main.py` keeps app creation, lifespan (catalog seeding, scheduler), the
  orchestrated `POST /api/rules` and `/api/health`, taking the container from `app.state` (set by `wire()`);
  `bootstrap.current()` and its global are removed; the scheduled sync receives the container explicitly.
- **Removed**: `app/stats.py` and the import-linter `ignore_imports` exception.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Pure refactor (`skip_specs: true`): `stats/financial-summary` keeps every requirement and scenario.

## Impact

- **Bounded contexts**: stats (migrated); transactions and banking gain one read-only public query each.
- **Cross-context events**: none added.
- **Security surface**: unchanged; the stats routes keep requiring a session.
- **Database**: unchanged; stats owns no tables.
- **Performance**: aggregation moves from SQL to Python over the movements of the requested period (and of all time
  for the history). Acceptable for a single user's volume (thousands of movements); if it ever is not, a stats-owned
  projection can replace the `MovementsSource` adapter without touching the domain.

### Out of scope

- An event-fed stats projection (decided against for now; the port keeps it possible).
- Any change to what stats computes, including the recorded observations (pending movements counted, balances summed
  across currencies).
