## MODIFIED Requirements

### Requirement: Transaction representation
Each transaction SHALL be exposed with `id`, `date`, `amount` (signed), `currency`, `status`, `counterparty`,
`description`, `kind`, `kind_manual`, `category_id`, `category_manual`, `account_id`, `account` (the account's alias or
name) and `note`. `raw` is not exposed.

#### Scenario: Listed transaction
- **WHEN** a €12.50 debit on the account aliased «Nómina» is listed
- **THEN** it appears with `amount` `-12.50` and `account` «Nómina», without `raw`

#### Scenario: Automatic kind
- **WHEN** a transaction whose kind was never set by hand is listed
- **THEN** it appears with `kind_manual` false

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Manual transfer mark (⇄)
**Reason**: It specified a known defect (the manual mark was not stored and was lost on the next sync or reprocess).
**Migration**: Replaced by «Stored manual kind (⇄)», which stores the mark and keeps it.
