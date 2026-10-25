## MODIFIED Requirements

### Requirement: Reprocessing from the original payload
The system SHALL allow reprocessing every transaction with `POST /api/reprocess`, which recomputes from `raw` every
normalized field (except the external id), the kind (transfer or normal) and the automatic category, and returns
`{"processed": <number of transactions>}`. It does not call Enable Banking. Imported transactions have no bank payload:
their fields stay as imported and only their automatic category is recomputed.

#### Scenario: Full reprocess
- **WHEN** reprocessing with 250 stored transactions
- **THEN** the response is `{"processed": 250}` and no request is made to Enable Banking

#### Scenario: The external id is kept
- **WHEN** a transaction is reprocessed
- **THEN** its external id does not change even if the id rule would now produce a different one

#### Scenario: New own account
- **WHEN** an own account's IBAN has been added and transactions are reprocessed
- **THEN** transactions whose counterparty has that IBAN become `transfer`

#### Scenario: Imported transaction
- **WHEN** an imported transaction is reprocessed
- **THEN** its date, amount and description stay as imported and its manual category or kind is kept
