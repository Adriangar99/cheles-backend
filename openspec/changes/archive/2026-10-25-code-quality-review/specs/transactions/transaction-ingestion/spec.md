## MODIFIED Requirements

### Requirement: Description, date and status
The system SHALL build the description by joining `remittance_information` with spaces or, if empty, from the
`bank_transaction_code` description, truncated to 1024 characters. The date is `booking_date`, falling back to
`value_date` then `transaction_date`; a transaction with none of them is skipped and logged, and the rest of the
batch is stored. The status is the received one, `BOOK` if missing.

#### Scenario: Several remittance lines
- **WHEN** `remittance_information` is `["COMPRA TARJETA", "MERCADONA VALENCIA"]`
- **THEN** the description is «COMPRA TARJETA MERCADONA VALENCIA»

#### Scenario: No remittance information
- **WHEN** there is no `remittance_information` and `bank_transaction_code.description` is «Recibo»
- **THEN** the description is «Recibo»

#### Scenario: No booking date
- **WHEN** `booking_date` is missing but `value_date` is present
- **THEN** the transaction's date is `value_date`

#### Scenario: Pending transaction
- **WHEN** the transaction has status `PDNG`
- **THEN** it is stored with status `PDNG`

#### Scenario: No date at all
- **WHEN** a sync receives two transactions and one has no `booking_date`, `value_date` or `transaction_date`
- **THEN** the dated one is stored, the undated one is skipped with a warning in the log, and the sync succeeds
