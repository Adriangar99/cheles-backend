# banking/bank-connection Specification

## Purpose

Lets the user link their banks through Enable Banking: pick a bank, authorize access on the bank's website and register
its accounts, reusing accounts already known from a previous connection.

## Requirements

### Requirement: List of available banks
The system SHALL return at `GET /api/banks/available` the banks Enable Banking offers for the configured country (ES
by default) and for personal customers, with each bank's `name`, `country` and `logo`.

#### Scenario: Available banks
- **WHEN** Enable Banking returns its bank list for the configured country
- **THEN** the response is a list with each bank's `name`, `country` and `logo`

#### Scenario: Enable Banking error
- **WHEN** Enable Banking responds with an error
- **THEN** the response is 502 with detail `Enable Banking: <error body>`

### Requirement: Starting authorization with a bank
The system SHALL start authorization with `POST /api/banks/connect` (`name`, optional `country` defaulting to the
configured one), storing a random pending `state` and requesting from Enable Banking a 180-day consent (configurable)
that redirects to `<PUBLIC_URL>/api/banks/callback`. It returns the bank's URL.

#### Scenario: Authorization started
- **WHEN** connecting the bank `BBVA` is requested
- **THEN** a pending authorization is stored with a random `state`, `BBVA` and the country
- **AND** the response is `{"url": <Enable Banking authorization url>}`

#### Scenario: Error while starting
- **WHEN** Enable Banking rejects the authorization request
- **THEN** the response is 502 with detail `Enable Banking: <error body>`

### Requirement: Authorization callback
The system SHALL handle `GET /api/banks/callback` (with the user's session): create the connection with the session
and expiry returned by Enable Banking, register its accounts, delete the pending authorization, run a first sync and
redirect (303) to `/bancos?connected=1`. Any failure redirects to `/bancos?error=1`.

#### Scenario: Authorization completed
- **WHEN** the callback arrives with a valid `code` and a known pending `state`
- **THEN** an active connection is created with the `session_id` and `valid_until` returned by Enable Banking
- **AND** every account in the session is linked to the connection with its Enable Banking `uid`
- **AND** the pending authorization is deleted and the response is 303 to `/bancos?connected=1`

#### Scenario: The bank returns an error or data is missing
- **WHEN** the callback carries `error`, has no `code`, or its `state` matches no pending authorization
- **THEN** the response is 303 to `/bancos?error=1` and no connection is created

#### Scenario: Session creation fails
- **WHEN** Enable Banking rejects the `code`
- **THEN** the response is 303 to `/bancos?error=1` and no connection is created

#### Scenario: The first sync fails
- **WHEN** the connection is created but the first sync raises an error
- **THEN** the error is logged and the response is still 303 to `/bancos?connected=1`

### Requirement: Re-linking known accounts on reconnection
When registering the accounts of a new connection, the system SHALL reuse an existing account whose
`identification_hash` matches or, failing that, whose normalized IBAN matches, keeping its role, alias and
transactions. If none matches, it creates a new account with the name given by the bank (or the bank's name) and its
currency (EUR by default).

#### Scenario: Reconnected account matched by hash
- **WHEN** an account arrives whose `identification_hash` already exists
- **THEN** the existing account moves to the new connection with the new `uid` and keeps its role, alias and transactions

#### Scenario: Reconnected account matched by IBAN
- **WHEN** the `identification_hash` does not match but the normalized IBAN matches an existing account
- **THEN** that account is reused and gets the received `identification_hash`

#### Scenario: New account
- **WHEN** neither the hash nor the IBAN match
- **THEN** an account is created with role `main`, the name given by the bank (or the bank's name if missing) and its currency

#### Scenario: The bank sends no IBAN
- **WHEN** a reused account arrives without an IBAN
- **THEN** it keeps its previously stored IBAN

### Requirement: Missing Enable Banking configuration
When the Enable Banking application id is not configured or its private key cannot be read, the system SHALL answer
503 with detail «Enable Banking no está configurado» to listing the available banks, starting an authorization,
syncing a connection and syncing every connection, without changing any stored connection. The authorization callback redirects to
`/bancos?error=1`.

#### Scenario: Listing banks without configuration
- **WHEN** `GET /api/banks/available` is requested without an application id configured
- **THEN** the response is 503 with detail «Enable Banking no está configurado»

#### Scenario: Connecting without a private key
- **WHEN** `POST /api/banks/connect` is requested and the private key file cannot be read
- **THEN** the response is 503 with detail «Enable Banking no está configurado»

#### Scenario: Syncing without configuration
- **WHEN** `POST /api/banks/{id}/sync` is requested for an active connection without an application id configured
- **THEN** the response is 503 with detail «Enable Banking no está configurado» and the connection's `last_error`,
  `status` and `last_synced_at` are unchanged

#### Scenario: Syncing everything without configuration
- **WHEN** `POST /api/sync` is requested with an active connection and no application id configured
- **THEN** the response is 503 with detail «Enable Banking no está configurado»

#### Scenario: Callback without configuration
- **WHEN** the authorization callback arrives with a valid code and state but Enable Banking is not configured
- **THEN** the browser is redirected to `/bancos?error=1`

### Requirement: Removing a connection
The system SHALL allow removing a connection with `DELETE /api/banks/{id}`: it asks Enable Banking to close the
session, marks the connection `revoked` and detaches its accounts, which keep their transactions, role, alias and IBAN
and appear in `detached_accounts`. Revoked connections are not listed or synced. If Enable Banking cannot close the
session, the error is logged and the connection is removed anyway.

#### Scenario: Remove a connection
- **WHEN** an active connection with two accounts is removed
- **THEN** the response is 204, Enable Banking is asked to delete its session, the connection no longer appears in
  `GET /api/banks` and both accounts appear in `detached_accounts` with their transactions and roles

#### Scenario: Enable Banking fails to close the session
- **WHEN** a connection is removed and Enable Banking answers an error
- **THEN** the error is logged and the connection is still removed

#### Scenario: Unknown connection
- **WHEN** an id that does not exist is removed
- **THEN** the response is 404

#### Scenario: Reconnecting after removing
- **WHEN** the same bank is connected again after removing its connection
- **THEN** its accounts are re-linked to the new connection by their identification hash, keeping role and alias

### Requirement: Abandoned authorizations are cleaned up
When an authorization is started, the system SHALL delete pending authorizations older than one hour, which belong to
bank flows that were abandoned or failed.

#### Scenario: Old pending authorization
- **WHEN** a pending authorization started two hours ago exists and a new authorization is started
- **THEN** the old one is deleted and the new one is stored

#### Scenario: Recent pending authorization
- **WHEN** a pending authorization started ten minutes ago exists and a new authorization is started
- **THEN** both are kept
