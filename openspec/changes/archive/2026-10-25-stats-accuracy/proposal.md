# Proposal

## Why

Two statistics observations recorded in `specs-base`, picked for block 2:

- **Edits on pending transactions are lost.** Pending (`PDNG`) transactions are deleted on every sync because the bank
  changes their id once booked, so a category, note or ⇄ mark set on a pending transaction disappears. The user chose
  to keep counting pending transactions (they are real spending) and to carry their edits over.
- **Currencies are mixed.** Balances and statistics add amounts regardless of currency; a dollar account would distort
  every figure. The user chose to count euros only and warn about anything left out.

## What Changes

- Ingestion keeps the deleted pending transactions of the account in memory and lets each received transaction that
  matches one (same account and amount, same counterparty or description, date within 3 days; external id first)
  inherit its manual category, note and manual kind.
- Statistics and balances count euros only; the summary gains `other_currencies` with the currencies left out.
- The transactions read model (`MovementRecord`) and banking's (`AccountSnapshot`) publish the currency, so stats can
  filter by it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `banking/bank-sync`: edits survive the replacement of pending transactions.
- `stats/financial-summary`: euros only, with `other_currencies`.

## Impact

- **Bounded contexts affected**: transactions (ingestion, domain matching, read model), banking (read model), stats
  (domain figures, summary, HTTP).
- **API**: `other_currencies` in the summary; `openapi.json` regenerated.
- **Persistence**: none.

### Out of scope

- Currency conversion; frontend warning (frontend change `fix-banks-and-errors`).
