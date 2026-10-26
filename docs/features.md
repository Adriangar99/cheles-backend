# Features

What the Cheles API does, by bounded context. The specs under `openspec/specs/` are the source of truth: each section
links to them, and every scenario there has a test.

## Identity — [user authentication](../openspec/specs/identity/user-authentication/spec.md)

- A single user, created from the command line with a password (12+ characters) and a TOTP secret (QR code).
- Login with username, password and 6-digit code; every failure answers the same «Datos incorrectos» after doing the
  same work, so neither the message nor the timing reveals what failed.
- Session in an `HttpOnly` cookie (14 days by default); at most 5 failed attempts per IP in 15 minutes.

## Banking — [bank connection](../openspec/specs/banking/bank-connection/spec.md), [bank sync](../openspec/specs/banking/bank-sync/spec.md), [accounts](../openspec/specs/banking/accounts/spec.md)

- Connect a bank through Enable Banking (180-day consent), re-linking known accounts on reconnection; the first sync
  runs in the background, so the bank's redirect is answered at once. Remove a connection (its accounts stay, without
  a bank).
- Automatic sync at 7:00 and 19:00 and on demand; incremental reads with an overlap window; balances; expired
  consents and provider errors recorded on the connection.
- Account roles (`main`, `savings`, `excluded`), alias and manual IBAN; IBAN changes reprocess every transaction.
- A missing Enable Banking configuration answers 503 «Enable Banking no está configurado».

## Transactions — [ingestion](../openspec/specs/transactions/transaction-ingestion/spec.md), [management](../openspec/specs/transactions/transaction-management/spec.md), [reprocessing](../openspec/specs/transactions/reprocessing/spec.md), [history import](../openspec/specs/transactions/history-import/spec.md)

- Transactions are stored exactly as the bank returns them (`raw`) and normalized (date, amount, counterparty,
  description); duplicates are detected by bank ids or a content hash; undated ones are skipped.
- Transfers between your own accounts (by IBAN) count as neither expense nor income.
- Each transaction has a readable `title`: «Traspaso a cuenta» / «Traspaso desde cuenta» for own transfers, the
  counterparty, or the merchant taken from BBVA's `sector // operation // detail` description.
- Listing with month, search, category, account and kind filters; manual category, manual transfer mark (⇄) and note,
  all kept by syncs and reprocessing, and carried over when a pending transaction is booked.
- Reprocessing recomputes everything from `raw` without calling the bank; imported transactions stay as imported.
- History import from a MoneyLover CSV export (`POST /api/imports/preview`, then `POST /api/imports`): each
  MoneyLover wallet goes to an existing account, a new account without a bank, or nowhere. On an account with a bank
  only rows before its first bank transaction are imported; importing again (or a newer export) adds only new rows;
  balance adjustments («Ajuste») are left out. Categories: MoneyLover's built-in ones through a fixed equivalence
  table, then the same name, then the automatic rules on the note. MoneyLover transfers come in as ordinary income
  and spending: mark the ones between your own accounts with ⇄.

## Categorization — [transaction categorization](../openspec/specs/categorization/transaction-categorization/spec.md)

- 16 default categories with pattern rules; user rules with higher priority (empty patterns are rejected); fallbacks for
  Bizum, other income and other expenses.

## Stats — [financial summary](../openspec/specs/stats/financial-summary/spec.md)

- Monthly income, expenses, net, savings and spending by category; 12-month history; balances by role.
- Only euros are counted; other currencies are reported as left out.

## Platform — [service runtime](../openspec/specs/platform/service-runtime/spec.md)

- Required `DATABASE_URL`, migrations on start (adopting databases created before migrations), health check.
