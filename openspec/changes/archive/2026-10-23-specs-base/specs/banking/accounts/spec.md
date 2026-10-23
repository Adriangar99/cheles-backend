# Spec Delta

## Purpose

Shows the bank connections and their accounts, and lets the user decide what each account is for (main, savings or
excluded), give it an alias and set its IBAN when the bank does not report it.

## ADDED Requirements

### Requirement: List of connections and accounts
The system SHALL return at `GET /api/banks` the connections ordered by id, each with `bank`, `status`, `valid_until`,
`last_synced_at`, `last_error` and its accounts, and separately in `detached_accounts` the accounts that belong to no
connection.

#### Scenario: Connections with accounts
- **WHEN** two connections with accounts exist
- **THEN** the response has `connections` ordered by id, each with its accounts

#### Scenario: Accounts without a connection
- **WHEN** an account has no associated connection
- **THEN** it appears in `detached_accounts`

### Requirement: Account representation
Each account SHALL be exposed with `id`, `name` (its alias if set, otherwise the bank's name for it), `iban_tail` (last
4 characters of the IBAN or null), `currency`, `role`, `balance`, `balance_at` and `connection_id`. The full IBAN is
never exposed.

#### Scenario: Account with an alias
- **WHEN** an account named «Cuenta Online» has the alias «Nómina»
- **THEN** its `name` is «Nómina»

#### Scenario: Hidden IBAN
- **WHEN** an account has the IBAN `ES9121000418450200051332`
- **THEN** its `iban_tail` is `1332` and the full IBAN does not appear in the response

### Requirement: Account role
The system SHALL allow changing an account's role with `PATCH /api/accounts/{id}` to `main` (day to day), `savings` or
`excluded` (does not count). New accounts have role `main`.

#### Scenario: Change the role
- **WHEN** `{"role": "savings"}` is sent
- **THEN** the account's role becomes `savings` and the response is the updated account

#### Scenario: Invalid role
- **WHEN** a role other than `main`, `savings` or `excluded` is sent
- **THEN** the response is 422 and the account is unchanged

#### Scenario: Unknown account
- **WHEN** an id that does not exist is patched
- **THEN** the response is 404

### Requirement: Account alias
The system SHALL allow setting an alias for the account. An empty alias removes it.

#### Scenario: Set an alias
- **WHEN** `{"alias": "Nómina"}` is sent
- **THEN** the account is shown with the name «Nómina»

#### Scenario: Remove the alias
- **WHEN** `{"alias": ""}` is sent
- **THEN** the account is shown with the bank's name again

### Requirement: Manual account IBAN
The system SHALL allow setting an account's IBAN, stored normalized (no spaces, uppercase); an empty IBAN removes it.
Changing the IBAN reprocesses every transaction, because it changes which ones are transfers between own accounts.

#### Scenario: Set the IBAN
- **WHEN** `{"iban": "es91 2100 0418 4502 0005 1332"}` is sent
- **THEN** `ES9121000418450200051332` is stored and every transaction is reprocessed

#### Scenario: Remove the IBAN
- **WHEN** `{"iban": ""}` is sent
- **THEN** the account has no IBAN and every transaction is reprocessed

#### Scenario: Changes without an IBAN
- **WHEN** only the role or the alias is changed
- **THEN** transactions are not reprocessed
