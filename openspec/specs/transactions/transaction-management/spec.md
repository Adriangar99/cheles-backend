# transactions/transaction-management Specification

## Purpose

Lets the user browse transactions with filters and correct them by hand (category, whether it is an own-account
transfer, and a note), so that the user's corrections take precedence over what is computed automatically.

## Requirements

### Requirement: Filtered transaction listing
The system SHALL list transactions at `GET /api/transactions`, newest first (by date, then by id descending), with
optional combinable filters `month` (`YYYY-MM`), `q`, `category_id`, `account_id` and `kind`, and pagination with
`limit` (100 by default, at most 500) and `offset`. Pending transactions are included.

#### Scenario: Filter by month
- **WHEN** `month=2026-09` is requested
- **THEN** only transactions dated between 2026-09-01 and 2026-09-30 are returned

#### Scenario: Text search
- **WHEN** `q=merca` is requested
- **THEN** transactions whose counterparty or description contain «merca», case-insensitively, are returned

#### Scenario: Malformed month
- **WHEN** `month=2026-9` is requested
- **THEN** the response is 422

#### Scenario: Limit exceeded
- **WHEN** `limit=1000` is requested
- **THEN** the response is 422

### Requirement: Transaction representation
Each transaction SHALL be exposed with `id`, `date`, `amount` (signed), `currency`, `status`, `title`, `counterparty`,
`description`, `kind`, `kind_manual`, `category_id`, `category_manual`, `account_id`, `account` (the account's alias or
name) and `note`. `raw` is not exposed.

#### Scenario: Listed transaction
- **WHEN** a €12.50 debit to «MERCADONA» on the account aliased «Nómina» is listed
- **THEN** it appears with `amount` `-12.50`, `title` «MERCADONA» and `account` «Nómina», without `raw`

#### Scenario: Automatic kind
- **WHEN** a transaction whose kind was never set by hand is listed
- **THEN** it appears with `kind_manual` false

### Requirement: Manual category
The system SHALL allow assigning an existing category by hand with `PATCH /api/transactions/{id}` (`category_id`),
marking it as manual so that sync and reprocessing do not change it. With `clear_category: true` the transaction goes
back to its automatic category and every transaction is reprocessed.

#### Scenario: Assign a category
- **WHEN** `{"category_id": 3}` is sent and category 3 exists
- **THEN** the transaction has category 3 with `category_manual` true

#### Scenario: Unknown category
- **WHEN** a `category_id` that does not exist is sent
- **THEN** the response is 400 «Categoría inexistente» and the transaction is unchanged

#### Scenario: The manual category is respected
- **WHEN** a transaction with a manual category is synced again or reprocessed
- **THEN** it keeps its category

#### Scenario: Back to the automatic category
- **WHEN** `{"clear_category": true}` is sent
- **THEN** `category_manual` becomes false, every transaction is reprocessed and the transaction gets its automatic category

#### Scenario: Unknown transaction
- **WHEN** an id that does not exist is patched
- **THEN** the response is 404

### Requirement: Transaction note
The system SHALL allow storing a note on a transaction with `note`; an empty note removes it.

#### Scenario: Add a note
- **WHEN** `{"note": "cena cumple"}` is sent
- **THEN** the transaction has the note «cena cumple»

#### Scenario: Remove the note
- **WHEN** `{"note": ""}` is sent
- **THEN** the transaction has no note

### Requirement: Stored manual kind (⇄)
The system SHALL allow setting a transaction's kind by hand to `transfer` or `normal` with `kind` in `PATCH
/api/transactions/{id}`. A kind that differs from the one derived from the counterparty IBAN is stored as manual
(`kind_manual` true) and kept by sync and reprocessing; a kind equal to the derived one clears the manual mark.

#### Scenario: Mark as transfer
- **WHEN** `{"kind": "transfer"}` is sent for a `normal` transaction whose counterparty is not an own account
- **THEN** the transaction becomes `transfer` with `kind_manual` true, has no category unless it had a manual one, and
  no longer counts as expense or income

#### Scenario: Remove a manual transfer mark
- **WHEN** `{"kind": "normal"}` is sent for a transaction manually marked `transfer` whose counterparty is not an own
  account
- **THEN** the transaction becomes `normal` with `kind_manual` false and gets its automatic category unless it had a
  manual one

#### Scenario: Mark a detected transfer as normal
- **WHEN** `{"kind": "normal"}` is sent for a transaction that is `transfer` because its counterparty is an own account
- **THEN** the transaction becomes `normal` with `kind_manual` true and gets its automatic category unless it had a
  manual one

#### Scenario: The mark survives a reprocess
- **WHEN** a transaction manually marked `transfer`, whose counterparty is not an own account, is reprocessed
- **THEN** it stays `transfer` with `kind_manual` true

#### Scenario: The mark survives a sync
- **WHEN** a transaction manually marked `transfer` arrives again within the sync window
- **THEN** it stays `transfer` with `kind_manual` true

### Requirement: Readable title
The system SHALL derive each transaction's `title`, in this order: a fixed text for transfers to or from the user's
own accounts (by counterparty IBAN); the counterparty; the merchant in the last segment of an `A // B // C`
description, cutting off city and country in the 40-character card format, or the previous segment when the last one
has no letters; the description. Imported transactions are titled by their description.

#### Scenario: Title from the counterparty
- **WHEN** a debit to «EXAMPLE MARKET» is listed
- **THEN** its `title` is «EXAMPLE MARKET»

#### Scenario: Card payment without counterparty
- **WHEN** a debit without creditor has the description
  `PAGO CON TARJETA EN GASOLINERAS // PAGO CON TARJETA // ACME FUEL                SOMECITY     ES`
- **THEN** its `title` is «ACME FUEL» and its `description` is unchanged

#### Scenario: Online merchant
- **WHEN** a debit without creditor has the description `PAGO CON TARJETA DE SERVICIOS VARIOS // OTROS // Example.com`
- **THEN** its `title` is «Example.com»

#### Scenario: Last segment without letters
- **WHEN** a debit without creditor has the description `CARGO POR AMORTIZACION // AMORTIZACIÓN PRÉSTAMO // 0000-1111-22`
- **THEN** its `title` is «AMORTIZACIÓN PRÉSTAMO»

#### Scenario: Transfer between own accounts
- **WHEN** a debit and a credit whose counterparty IBAN is an own account's IBAN are listed
- **THEN** their titles are «Traspaso a cuenta» and «Traspaso desde cuenta»

#### Scenario: Unstructured description
- **WHEN** a credit without debtor has the description «NOMINA EMPRESA»
- **THEN** its `title` is «NOMINA EMPRESA»

#### Scenario: Imported transaction title
- **WHEN** an imported transaction with the note «Cena con amigos» is listed
- **THEN** its `title` is «Cena con amigos»
