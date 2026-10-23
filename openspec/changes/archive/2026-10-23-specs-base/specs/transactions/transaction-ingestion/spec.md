# Spec Delta

## Purpose

Turns each transaction exactly as Enable Banking delivers it (`raw`) into a Cheles transaction, keeping the original so
it can be reprocessed, and tells transfers between the user's own accounts apart from real expenses and income.

## ADDED Requirements

### Requirement: Keeping the original transaction
The system SHALL store, alongside each transaction, the bank's original payload (`raw`) unmodified, so that every
derived field can be recomputed from it without requesting it again.

#### Scenario: Raw stored
- **WHEN** a transaction received from Enable Banking is stored
- **THEN** its `raw` is identical to the received object

### Requirement: Signed amount
The system SHALL store the amount with a sign: negative when money goes out (`credit_debit_indicator` = `DBIT`) and the
received value otherwise. The currency is the amount's currency, EUR if missing.

#### Scenario: Debit
- **WHEN** an amount of `12.50` arrives with indicator `DBIT`
- **THEN** the stored amount is `-12.50`

#### Scenario: Credit
- **WHEN** an amount of `1500.00` arrives with indicator `CRDT`
- **THEN** the stored amount is `1500.00`

#### Scenario: No currency
- **WHEN** the amount has no currency
- **THEN** the currency is `EUR`

### Requirement: Transaction counterparty
The system SHALL take the creditor as counterparty for debits and the debtor for credits, storing its name and its
normalized IBAN (no spaces, uppercase), or null when missing.

#### Scenario: Counterparty of a debit
- **WHEN** a debit has `creditor.name` «MERCADONA» and `debtor.name` «Ana»
- **THEN** the counterparty is «MERCADONA»

#### Scenario: Counterparty of a credit
- **WHEN** a credit has `debtor.name` «EMPRESA SL» and `debtor_account.iban` `es12 3456`
- **THEN** the counterparty is «EMPRESA SL» with IBAN `ES123456`

### Requirement: Description, date and status
The system SHALL build the description by joining `remittance_information` with spaces or, if empty, from the
`bank_transaction_code` description, truncated to 1024 characters. The date is `booking_date`, falling back to
`value_date` then `transaction_date`. The status is the received one, `BOOK` if missing.

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

### Requirement: Stable external id
The system SHALL identify each transaction within its account with `ref:<entry_reference>` if present, otherwise
`id:<transaction_id>`, otherwise `h:` followed by the first 32 hex characters of the SHA-256 of
`<date>|<signed amount>|<description>`, using the full description before truncation.

#### Scenario: With a bank reference
- **WHEN** the transaction has `entry_reference` `ABC123`
- **THEN** its external id is `ref:ABC123`

#### Scenario: Only a transaction id
- **WHEN** there is no `entry_reference` but there is a `transaction_id` `T9`
- **THEN** its external id is `id:T9`

#### Scenario: No bank identifiers
- **WHEN** there is neither `entry_reference` nor `transaction_id`
- **THEN** the id is `h:` plus a hash of date, amount and description, identical for identical data

### Requirement: Detecting transfers between own accounts
The system SHALL mark a transaction as `transfer` when its counterparty IBAN matches the IBAN of any registered own
account (whatever its role), and as `normal` otherwise. Transfers get no automatic category.

#### Scenario: Transfer to the savings account
- **WHEN** a debit's counterparty IBAN is another own account
- **THEN** the transaction is `transfer` and has no category

#### Scenario: Payment to a third party
- **WHEN** the counterparty IBAN belongs to no own account, or there is no IBAN
- **THEN** the transaction is `normal` and gets an automatic category

#### Scenario: Excluded account
- **WHEN** the counterparty IBAN belongs to an own account with role `excluded`
- **THEN** the transaction is also `transfer`
