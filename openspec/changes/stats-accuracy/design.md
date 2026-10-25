# Design

## Context

See proposal.md. `Ingest` calls `delete_pending(account_id)` and then stores each payload; `derive()` keeps manual
category and kind. `MovementRecord` (transactions) and `AccountSnapshot` (banking) carry no currency; stats builds
`Movement` and `AccountStanding` from them through the adapters in `bootstrap.py`.

## Goals / Non-Goals

**Goals:** pending edits survive booking and re-sending; figures never mix currencies.

**Non-Goals:** conversion; editing restrictions on pending transactions.

## Decisions

### Matching pending transactions (transactions domain)
- `delete_pending()` returns the deleted transactions (`pop_pending()`), still in the same unit of work.
- A pure function `inherit_edits(incoming, removed_pendings, used)`: candidates are removed pendings of the same
  account with the same `amount` (Money) and the same counterparty (case-insensitive) or, when both have none, the same
  description; the date difference must be ≤ 3 days. An exact external-id match wins; otherwise the closest date, then
  the lowest id. The chosen pending is marked used. Copied: `category_id` + `category_manual` when manual, `note`,
  `kind` + `kind_manual` when manual.
- `Ingest` applies it to each newly created transaction before `derive()`, so derived fields respect the inherited
  manual flags.

### Euros only (stats domain)
- `MovementRecord.currency` and `AccountSnapshot.currency` are published; the adapters fill `Movement.currency` and
  `AccountStanding.currency`.
- `counted()` keeps `currency == "EUR"`; `balances_by_role()` sums EUR accounts only; `other_currencies()` collects the
  non-EUR currencies of the month's otherwise-counted movements and of non-excluded accounts with a balance.
- `SummaryOut.other_currencies: list[str]`.

## Risks / Trade-offs

- [A wrong match copies edits to another transaction] → The match needs the same account, the same exact amount and
  counterparty and a near date; each pending is used once.
- [History also drops non-EUR] → Consistent with the summary; the warning names the currency.

## Migration Plan

Code-only; regenerate `openapi.json`. Rollback: revert the PR.
