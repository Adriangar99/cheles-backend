# Design

## Context

See proposal.md. Current `app/stats.py` (SQL over `transactions` joined with `accounts`):

- counted = `kind == "normal"` and account role `!= "excluded"` (pending included);
- `month_summary`: income = sum of counted amounts `> 0`; expenses = −(sum of counted amounts `< 0`); net = income +
  (signed) expenses; saved = sum of `transfer` amounts on `savings` accounts in the month (no counted filter);
  spending by category = counted debits grouped by `category_id`, ordered by signed sum ascending (largest spending
  first), labelled through categorization, `NULL` → «Sin categoría», «•», `#8a8a8a`;
- `monthly_history(months)`: per `YYYY-MM` with counted movements, income and expenses, the latest `months` months in
  chronological order;
- `total_balance`: sum of balances (null as 0) per role excluding `excluded`, plus `total`; roles without accounts
  absent.
- Routes in `app/main.py`: summary (month defaults to today, `^\d{4}-\d{2}$`) returns the summary plus `balances`;
  history (`months` default 12, `le=60`).
- `bootstrap.current()` is used by stats, the lifespan, `scheduled_sync` and `POST /api/rules`.

## Goals / Non-Goals

**Goals:** identical JSON output and ordering; stats depends only on its ports; no import-linter exception; no
service locator.

**Non-Goals:** a persisted read model; changing the computed figures.

## Decisions

### Read models published by the owners
- `app.transactions.public`: `MovementRecord` (frozen dataclass: `account_id`, `booking_date`, `amount: Decimal`
  signed, `kind`, `category_id`) and the use case `ListMovements(start: date | None, end: date | None)` — a
  repository query returning only these fields. It is transactions' published language: stats never sees
  `Transaction`, the raw payload or notes.
- `app.banking.public`: `AccountSnapshot(account_id, role, balance: Decimal | None)` and `AccountSnapshots()`.
- Categorization's `CategoryLabels(ids)` is reused as is.

### Stats domain (`app/stats/domain/`)
- `Movement` and `AccountStanding` are stats' own views of the inputs. `AccountStanding.counts` is `role !=
  "excluded"` and `is_savings` is `role == "savings"`: stats translates banking's role into the two facts it cares
  about at its boundary (adapter), so the rest of stats never interprets roles.
- `figures.py`: pure functions `counted(movements, standings)`, `month_summary(...)`, `spending_by_category(...)`,
  `history(...)`, `balances_by_role(...)`, written to match the SQL semantics above exactly (sum of nothing is
  `Decimal(0)`; stable ordering by signed sum; months as `YearMonth`).
- The uncategorized label stays a stats presentation default.

### Stats application (`app/stats/application/`)
Ports: `MovementsSource.between(start, end)`, `AccountsSource.standings()` (returns standings and balances by role),
`CategoryLabelsSource.labels(ids)`, `Clock.today()`. Use cases: `MonthlySummary(month: YearMonth | None)` (defaults to
the clock's current month) returning figures + balances, and `MonthlyHistory(months)`.

### Composition edge without a service locator
`wire(app, container)` stores the container in `app.state.container` (and keeps the dependency overrides). `main.py`
reads it in the lifespan (seeding, scheduler job with the container passed as argument) and in `POST /api/rules`
through a small dependency. `bootstrap.current()` and the module global are deleted. Tests that called
`app.main.scheduled_sync()` pass the test container.

### Contracts
The contexts list gains `stats`; the legacy list becomes `app.main`, `app.cli`; the `ignore_imports` exception is
removed. `app.stats` must import nothing from other contexts (its adapters live in `app/bootstrap.py`).

### Tests
Characterization tests (`stats/financial-summary`) keep their expected values and are the acceptance check. New unit
tests for `figures.py`, because the aggregation logic is rewritten from SQL to Python: counted filter, savings
(including withdrawals), spending order and the uncategorized group, history (latest N with data, chronological,
empty months omitted), balances by role (null balance as 0, excluded omitted, roles without accounts absent).

## Risks / Trade-offs

- [Python aggregation over all movements for the history] → Linear in the number of movements; fine for one user. The
  port allows a projection later.
- [Several sessions per stats request (one per source)] → Read-only; acceptable.
- [Semantic drift SQL → Python] → Unit tests mirror the SQL semantics and the characterization tests guard the HTTP
  output.

## Migration Plan

Refactor only; rebuild the image. No data or schema change.
