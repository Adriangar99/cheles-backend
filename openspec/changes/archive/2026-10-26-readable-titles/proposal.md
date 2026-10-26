# Proposal

## Why

Transaction titles are unreadable (issue #32). The web app labels each movement with its counterparty or, failing
that, its whole description. BBVA card payments without a creditor show the whole remittance text, cut before the
useful part:

```
PAGO CON TARJETA EN GASOLINERAS // PAGO CON TARJETA // ACME FUEL                SOMECITY     ES
```

Transfers between the user's own accounts show the user's own name as counterparty. The title has to be derived once,
in the backend, where the bank format is known.

## What Changes

- Every listed (or edited) transaction gains a `title`, derived from data that is already stored:
  - a transfer to or from one of the user's own accounts (counterparty IBAN among the own IBANs): «Traspaso a cuenta»
    (debit) or «Traspaso desde cuenta» (credit);
  - otherwise the counterparty, when the bank sends one;
  - otherwise, for the `A // B // C` remittance format, the merchant in the last segment (fixed-width card format:
    the first 25 characters, without city and country), or the previous segment when the last one has no letters
    (e.g. a loan number);
  - otherwise the description. Imported transactions keep their description (a note written by the user).
- `description` stays as it is, as the detail.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `transactions/transaction-management`: `title` in the transaction representation and how it is derived.

## Impact

- **Bounded contexts affected**: transactions (domain, use cases, HTTP).
- **Cross-context events**: none added or changed. The title uses the own IBANs that transactions already obtains
  from banking through its `OwnAccounts` port.
- **API**: new `title` field in `GET /api/transactions` and `PATCH /api/transactions/{id}`; `openapi.json`
  regenerated.
- **Persistence**: none. The title is computed when reading, so existing transactions get it with no reprocess.
- **Security surface**: none.

### Out of scope

- Using the title in the web app and showing the full text of truncated texts on hover (frontend change).
- Seeding automatic categorization with BBVA's merchant sector (first segment).
- Text search on the title (`q` keeps searching counterparty and description).
- Recognising the holder's name as counterparty when the other account is not connected.
