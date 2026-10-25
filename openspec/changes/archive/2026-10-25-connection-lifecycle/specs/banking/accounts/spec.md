## MODIFIED Requirements

### Requirement: List of connections and accounts
The system SHALL return at `GET /api/banks` the connections that are not `revoked`, ordered by id, each with `bank`,
`country`, `status`, `valid_until`, `last_synced_at`, `last_error` and its accounts, and separately in
`detached_accounts` the accounts that belong to no connection.

#### Scenario: Connections with accounts
- **WHEN** two connections with accounts exist
- **THEN** the response has `connections` ordered by id, each with its accounts

#### Scenario: Accounts without a connection
- **WHEN** an account has no associated connection
- **THEN** it appears in `detached_accounts`

#### Scenario: Country of a connection
- **WHEN** a connection with Revolut was authorized for country `LT`
- **THEN** it is listed with `country` `LT`
