# Spec Delta

## Purpose

Recomputes every stored transaction from its original `raw` payload, to apply changes to rules, own accounts or
normalization without requesting data from the bank again and without losing what the user corrected by hand.

## ADDED Requirements

### Requirement: Reprocessing from the original payload
The system SHALL allow reprocessing every transaction with `POST /api/reprocess`, which recomputes from `raw` every
normalized field (except the external id), the kind (transfer or normal) and the automatic category, and returns
`{"processed": <number of transactions>}`. It does not call Enable Banking.

#### Scenario: Full reprocess
- **WHEN** reprocessing with 250 stored transactions
- **THEN** the response is `{"processed": 250}` and no request is made to Enable Banking

#### Scenario: The external id is kept
- **WHEN** a transaction is reprocessed
- **THEN** its external id does not change even if the id rule would now produce a different one

#### Scenario: New own account
- **WHEN** an own account's IBAN has been added and transactions are reprocessed
- **THEN** transactions whose counterparty has that IBAN become `transfer`

### Requirement: Reprocessing respects manual edits
Reprocessing SHALL keep manually assigned categories and notes. The kind is always recomputed (see the known defect in
`transactions/transaction-management`).

#### Scenario: Manual category
- **WHEN** a transaction with a manual category is reprocessed
- **THEN** it keeps its category

#### Scenario: Note
- **WHEN** a transaction with a note is reprocessed
- **THEN** it keeps its note

### Requirement: Actions that trigger a reprocess
The system SHALL reprocess every transaction after an account's IBAN changes, after a categorization rule is created
and after a transaction is sent back to its automatic category.

#### Scenario: Creating a rule
- **WHEN** a new rule is created
- **THEN** every transaction is reprocessed and the rule applies to the whole history
