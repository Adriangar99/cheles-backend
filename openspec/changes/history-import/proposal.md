# Proposal

## Why

Block 7 of the roadmap. The bank only returns recent history, but the user kept their finances in MoneyLover before
connecting the bank. Importing that export gives «mi mes», «movimientos» and the history chart the months before the
bank connection, without duplicating what the bank already brought.

## What Changes

- **MoneyLover CSV reader** (anti-corruption layer): UTF-16 or UTF-8 export with columns `Id, Fecha, Categoria,
  Cantidad, Moneda, Nota, Cuenta`; dates `dd/mm/yyyy`, signed amounts with a decimal point. MoneyLover's `Id` is renumbered
  on every export, so each row gets a stable id from its content.
- **Preview** `POST /api/imports/preview`: per MoneyLover wallet (`Cuenta`), how many rows, their date range, and with the
  chosen target account how many would be imported, how many fall on or after the account's first bank transaction
  (skipped: the bank already has them) and how many were imported before; plus the MoneyLover categories without an
  equivalent. Writes nothing.
- **Import** `POST /api/imports`: the same input; creates an account without a bank for wallets sent to «new», stores the
  rows as imported transactions and returns the counts.
- **Categories**: a fixed equivalence table for MoneyLover's built-in categories, then a match by name (ignoring case
  and accents), then the automatic rules on the note. «Transferencia entrante/saliente» become transfers (⇄).
- **Reprocessing** keeps imported transactions as imported (there is no bank payload to rebuild them from); their
  automatic category is recomputed.
- Transactions get a `source` (`bank` or `import`), migration `0003_transaction_source`.

## Capabilities

### New Capabilities

- `transactions/history-import`: reading a MoneyLover export, preview and import.

### Modified Capabilities

- `transactions/reprocessing`: imported transactions are not rebuilt from a payload.

## Impact

- **Contexts**: transactions (reader, use cases, HTTP), banking (creating an account without a bank, through its public
  API), categorization (category names, through its public API).
- **API**: two new endpoints; `openapi.json` regenerated.
- **Database**: migration `0003_transaction_source` (default `bank`).
- **Security surface**: the file travels in the request body (base64, at most 5 MB decoded) and is never stored; the
  endpoints require the session like every other.

### Out of scope

- Other apps' formats (the reader is chosen by the header, so another one can be added later).
- Editing the equivalence table from the UI; balances of imported accounts.
