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
Each transaction SHALL be exposed with `id`, `date`, `amount` (signed), `currency`, `status`, `counterparty`,
`description`, `kind`, `category_id`, `category_manual`, `account_id`, `account` (the account's alias or name) and
`note`. `raw` is not exposed.

#### Scenario: Listed transaction
- **WHEN** a €12.50 debit on the account aliased «Nómina» is listed
- **THEN** it appears with `amount` `-12.50` and `account` «Nómina», without `raw`

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

### Requirement: Manual transfer mark (⇄)
The system SHALL allow changing a transaction's kind by hand to `transfer` or `normal` with `kind`. The mark is not
stored as manual (known defect): the next sync that includes the transaction, or any reprocess, recomputes it from the
counterparty's IBAN.

#### Scenario: Mark as transfer
- **WHEN** `{"kind": "transfer"}` is sent for a `normal` transaction
- **THEN** the transaction becomes `transfer` and no longer counts as expense or income

#### Scenario: The mark is lost on reprocess (known defect)
- **WHEN** a transaction manually marked `transfer`, whose counterparty is not an own account, is reprocessed
- **THEN** it becomes `normal` again and gets an automatic category unless it had a manual one

#### Scenario: The mark is lost on sync (known defect)
- **WHEN** a transaction manually marked `transfer` arrives again within the sync window
- **THEN** its kind is recomputed and it becomes `normal` again if the counterparty is not an own account

### Requirement: Transaction note
The system SHALL allow storing a note on a transaction with `note`; an empty note removes it.

#### Scenario: Add a note
- **WHEN** `{"note": "cena cumple"}` is sent
- **THEN** the transaction has the note «cena cumple»

#### Scenario: Remove the note
- **WHEN** `{"note": ""}` is sent
- **THEN** the transaction has no note
