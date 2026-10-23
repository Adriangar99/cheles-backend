# banking/bank-sync Specification

## Purpose

Keeps the linked accounts' transactions and balances up to date by reading from Enable Banking, on a schedule or on
demand, and reflects on each connection its status, its last error and whether its consent has expired.

## Requirements

### Requirement: Scheduled sync
The system SHALL automatically sync every connection with status `active` at the configured hours (7 and 19 by
default, Europe/Madrid local time). A failure during the scheduled sync is logged and does not stop the API.

#### Scenario: Scheduled run
- **WHEN** one of the configured hours arrives
- **THEN** every `active` connection is synced and the number of new transactions is logged

#### Scenario: Inactive connections
- **WHEN** a connection is `expired` or `revoked`
- **THEN** the scheduled sync skips it

### Requirement: Manual sync
The system SHALL allow syncing one connection with `POST /api/banks/{id}/sync`, returning `new` (new transactions),
`status` and `error` of the connection, and every active connection with `POST /api/sync`, returning `new`.

#### Scenario: Sync one connection
- **WHEN** an existing connection is synced
- **THEN** the response is `{"new": <n>, "status": <status>, "error": <last error or null>}`

#### Scenario: Unknown connection
- **WHEN** an id that does not exist is synced
- **THEN** the response is 404

#### Scenario: Sync everything
- **WHEN** `POST /api/sync` is called
- **THEN** every `active` connection is synced and the response is `{"new": <total new transactions>}`

### Requirement: Expired consent
Before reading, the system SHALL check the consent's expiry: if `valid_until` is in the past, the connection becomes
`expired` and nothing is requested from Enable Banking.

#### Scenario: Consent past its expiry
- **WHEN** a connection whose `valid_until` is earlier than now is synced
- **THEN** the connection becomes `expired`, 0 new transactions are returned and Enable Banking is not called
- **AND** `last_synced_at` is not updated

### Requirement: Incremental read window
For each account of the connection with an Enable Banking `uid`, the system SHALL request transactions starting 10
days before the latest stored booked (`BOOK`) transaction, or 730 days back (configurable) if there is none, following
every page Enable Banking returns. Accounts without a `uid` are skipped.

#### Scenario: Account with history
- **WHEN** the account's latest booked transaction is dated 2026-10-20
- **THEN** transactions are requested from 2026-10-10

#### Scenario: First read
- **WHEN** the account has no booked transactions
- **THEN** transactions are requested from 730 days ago

#### Scenario: Pagination
- **WHEN** Enable Banking returns a `continuation_key`
- **THEN** further pages are requested with that key until none is returned

### Requirement: Storing transactions without duplicates
The system SHALL store each received transaction keyed by account and external id: if it already exists it is updated
with the received data, otherwise it is created. A transaction counts as new only when it is created.

#### Scenario: Repeated transaction in the overlap window
- **WHEN** a transaction arrives whose external id already exists in that account
- **THEN** the existing one is updated, no duplicate is created and it does not count as new

#### Scenario: New transaction
- **WHEN** a transaction arrives with an external id unknown to the account
- **THEN** it is created with its derived fields (kind and automatic category) and counts as new

### Requirement: Replacing pending transactions
On every read of an account, the system SHALL delete its pending (`PDNG`) transactions before storing the received
ones, because the bank changes their id once they are booked.

#### Scenario: Pending transaction gets booked
- **WHEN** an account had a `PDNG` transaction and the bank now returns it as `BOOK` with a different id
- **THEN** after the sync only the `BOOK` transaction exists

#### Scenario: Pending transaction is still pending
- **WHEN** the bank returns the same transaction as `PDNG` again
- **THEN** the previous one is deleted and created again, losing any manual edit it had

### Requirement: Account balance
After reading an account's transactions, the system SHALL store its balance and the read time, choosing the first
available type in this order: `ITAV`, `CLAV`, `XPCD`, `ITBD`, `CLBD`. If none is present it uses the first balance
received, and if there are no balances it leaves the balance empty.

#### Scenario: Preferred balance
- **WHEN** the bank returns `CLBD` and `ITAV` balances
- **THEN** the `ITAV` amount is stored

#### Scenario: Unrecognized type
- **WHEN** the bank only returns a balance of type `OTHR`
- **THEN** that amount is stored

#### Scenario: No balances
- **WHEN** the bank returns no balances
- **THEN** the balance is empty and the read time is updated

### Requirement: Enable Banking errors during sync
If Enable Banking responds with an error while syncing a connection, the system SHALL store the error in `last_error`
(at most 1024 characters), mark the connection `expired` if the status code is 401 or 403, and update
`last_synced_at`. Data of accounts already stored before the error is kept, and the remaining accounts are not read.

#### Scenario: Transient error
- **WHEN** Enable Banking responds 500 while reading an account
- **THEN** the connection stores the error in `last_error`, stays `active` and updates `last_synced_at`
- **AND** that account's changes are not stored

#### Scenario: Access revoked
- **WHEN** Enable Banking responds 401 or 403
- **THEN** the connection becomes `expired` and stores the error

#### Scenario: Error on the second account
- **WHEN** the first account is read successfully and the second one fails
- **THEN** the first account's transactions and balance are kept
- **AND** any account after the second one is not read in that sync

#### Scenario: Successful sync after an error
- **WHEN** a connection with a `last_error` syncs without errors
- **THEN** `last_error` is cleared
