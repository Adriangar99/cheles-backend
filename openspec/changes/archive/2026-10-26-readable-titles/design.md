# Design

## Context

See proposal.md. `normalize` (the Enable Banking ACL in `transactions/domain/bank_payload.py`) builds the description
by joining the remittance lines, and takes the counterparty from `creditor`/`debtor` by direction. `Transaction`
already knows whether its counterparty IBAN is an own IBAN (`_automatic_kind`). `ListTransactions` and
`EditTransaction` build a `TransactionView` with the account's display name through the `OwnAccounts` port, which also
serves the own IBANs.

What the bank data looks like (BBVA): the remittance has three segments, `sector // operation // detail`. For card
payments the detail is fixed-width: merchant (25), city (13), country (2). A merchant name that fills its 25
characters runs straight into the city, so collapsing spaces cannot separate them; cutting at 25 can. Online merchants
send a shorter detail with no city. Some details are only numbers (loan or ATM references), and the middle segment
then names the operation.

## Goals / Non-Goals

**Goals:** a readable title for every transaction, including those already stored, with no schema change.

**Non-Goals:** categorization from the sector; per-bank parsers beyond the `A // B // C` format.

## Decisions

### Computed when reading, not stored
`Transaction.title(own_ibans)` derives it from fields already stored (`counterparty`, `counterparty_iban`,
`description`, `amount`, `source`). Storing it would need a migration and a reprocess, and a new own IBAN would leave
stored titles stale until the next reprocess. Its cost is one call to `OwnAccounts.ibans()` per listing.

### The own-transfer check uses the IBAN, not the kind
The title says who is on the other side, so it uses the same own-IBAN test as the automatic kind, not `kind`: a
movement marked ⇄ by hand to a third party keeps its counterparty as title.

### Remittance parsing lives in the ACL
`remittance_title(description)` in `bank_payload.py`, next to the code that builds the description, since it knows the
bank's format. It returns `None` when the description is not in the `A // B // C` format, and `Transaction.title`
then falls back to the description.

### `title` in the view
`TransactionView` gains `title`; the HTTP adapter adds it to `TransactionOut`. No value object: it is a plain display
string with no rules of its own.

## Risks / Trade-offs

- [A bank changes its format] → The title falls back to the counterparty or the description; nothing is lost.
- [A detail exactly 40 characters long that is not the card format] → It would be cut at 25. In the stored data every
  40-character detail is a card payment.

## Migration Plan

Code-only, no Alembic migration. `openapi.json` regenerated (new field). Rollback: revert the PR.
