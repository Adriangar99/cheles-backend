# Spec Delta

## Purpose

Summarizes the user's finances: how much comes in, how much goes out and where it goes each month, how much is set
aside as savings, the trend over recent months and the current balance, counting only money that really comes in or
goes out.

## ADDED Requirements

### Requirement: Counted transactions
Income and expense statistics SHALL only count transactions of kind `normal` from accounts whose role is not
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

### Requirement: Monthly summary
The system SHALL return at `GET /api/stats/summary?month=YYYY-MM` (current month by default) the month's `income` (sum
of positive amounts), `expenses` (sum of negative amounts, as a positive number) and `net` (income minus expenses),
together with balances by role.

#### Scenario: Month with transactions
- **WHEN** 2026-09 has €2000 of income and €1200 of debits
- **THEN** the response has `income` 2000, `expenses` 1200 and `net` 800

#### Scenario: Month without transactions
- **WHEN** the month has no counted transactions
- **THEN** `income`, `expenses` and `net` are 0

#### Scenario: Malformed month
- **WHEN** `month=09-2026` is requested
- **THEN** the response is 422

### Requirement: Monthly savings
The summary SHALL include `saved`: the sum of the amounts of own-account transfers recorded on accounts with role
`savings` during the month (what goes into savings minus what comes out).

#### Scenario: Contribution to savings
- **WHEN** the savings account receives a €300 own-account transfer in the month
- **THEN** `saved` is 300

#### Scenario: Withdrawal from savings
- **WHEN** in the month the savings account receives €300 and sends €500 to other own accounts
- **THEN** `saved` is -200

### Requirement: Spending by category
The summary SHALL include `by_category`: the month's debits grouped by category, with `id`, `name`, `icon`, `color` and
`amount` (positive), from highest to lowest spending. Uncategorized debits are grouped as «Sin categoría» with null id,
icon «•» and color `#8a8a8a`. Income does not appear.

#### Scenario: Spending breakdown
- **WHEN** the month has €300 in Supermercado and €120 in Restaurantes
- **THEN** `by_category` lists Supermercado with 300 followed by Restaurantes with 120

#### Scenario: Uncategorized debit
- **WHEN** a counted debit has no category
- **THEN** it is grouped under «Sin categoría»

### Requirement: Monthly history
The system SHALL return at `GET /api/stats/history?months=N` (12 by default, at most 60) the income and expenses of the
last N months that have counted transactions, in chronological order. Months without transactions are omitted.

#### Scenario: Last months
- **WHEN** the history is requested with `months=3` and there is data from January to September
- **THEN** July, August and September are returned, in that order, with `month`, `income` and `expenses`

#### Scenario: Month without transactions
- **WHEN** August has no counted transactions
- **THEN** August does not appear in the history

#### Scenario: Limit exceeded
- **WHEN** `months=61` is requested
- **THEN** the response is 422

### Requirement: Balances by role
The summary SHALL include `balances`: the sum of the last known balance of the accounts of each role (`main`,
`savings`), excluding `excluded` accounts, plus `total` with the sum of all. Roles without accounts are omitted and
currencies are not distinguished.

#### Scenario: Balances
- **WHEN** there is a `main` account with €1000, a `savings` account with €5000 and an `excluded` account with €200
- **THEN** `balances` is `{"main": 1000, "savings": 5000, "total": 6000}`
