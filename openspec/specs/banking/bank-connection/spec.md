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
