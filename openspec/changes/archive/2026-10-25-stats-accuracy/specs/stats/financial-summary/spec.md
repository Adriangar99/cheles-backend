## MODIFIED Requirements

### Requirement: Counted transactions
Income and expense statistics SHALL only count transactions in euros of kind `normal` from accounts whose role is not
`excluded`. Pending transactions are included.

#### Scenario: Own-account transfer
- **WHEN** there is a €500 transfer between own accounts in the month
- **THEN** it adds to neither income nor expenses

#### Scenario: Excluded account
- **WHEN** an account with role `excluded` has a €30 debit
- **THEN** it does not add to expenses

#### Scenario: Pending transaction
- **WHEN** there is a pending €20 debit in the month
- **THEN** it adds to the month's expenses

#### Scenario: Another currency
- **WHEN** a counted account has a $40 debit in the month
- **THEN** it adds to neither income nor expenses

### Requirement: Balances by role
The summary SHALL include `balances`: the sum of the last known balance of the euro accounts of each role (`main`,
`savings`), excluding `excluded` accounts, plus `total` with the sum of all. Roles without accounts are omitted.

#### Scenario: Balances
- **WHEN** there is a `main` account with €1000, a `savings` account with €5000 and an `excluded` account with €200
- **THEN** `balances` is `{"main": 1000, "savings": 5000, "total": 6000}`

#### Scenario: Account in another currency
- **WHEN** there is also a `main` account with a balance of $300
- **THEN** `balances` is still `{"main": 1000, "savings": 5000, "total": 6000}`

## ADDED Requirements

### Requirement: Amounts left out by currency
The summary SHALL include `other_currencies`: the sorted currency codes, other than EUR, of the month's transactions
and the account balances that would otherwise have been counted, so the user knows the figures leave them out. It is
empty when everything is in euros.

#### Scenario: Everything in euros
- **WHEN** every counted transaction and balance is in euros
- **THEN** `other_currencies` is `[]`

#### Scenario: Dollars left out
- **WHEN** a counted account in USD has a balance or a transaction in the month
- **THEN** `other_currencies` is `["USD"]`
