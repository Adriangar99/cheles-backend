## MODIFIED Requirements

### Requirement: Detecting transfers between own accounts
The system SHALL mark a transaction as `transfer` when its counterparty IBAN matches the IBAN of any registered own
account (whatever its role), and as `normal` otherwise, unless its kind was set by hand. Transfers get no automatic
category.

#### Scenario: Transfer to the savings account
- **WHEN** a debit's counterparty IBAN is another own account
- **THEN** the transaction is `transfer` and has no category

#### Scenario: Payment to a third party
- **WHEN** the counterparty IBAN belongs to no own account, or there is no IBAN
- **THEN** the transaction is `normal` and gets an automatic category

#### Scenario: Excluded account
- **WHEN** the counterparty IBAN belongs to an own account with role `excluded`
- **THEN** the transaction is also `transfer`

#### Scenario: Manual kind kept on ingestion
- **WHEN** a transaction manually marked `normal` whose counterparty is an own account is received again
- **THEN** it stays `normal` and keeps `kind_manual` true
