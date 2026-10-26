## MODIFIED Requirements

### Requirement: Authorization callback
The system SHALL handle `GET /api/banks/callback` (with the user's session): create the connection with the session
and expiry returned by Enable Banking, register its accounts, delete the pending authorization and redirect (303) to
`/bancos?connected=1` without waiting for the first sync, which runs in the background once the response has been
sent. Any failure before the connection is created redirects to `/bancos?error=1`.

#### Scenario: Authorization completed
- **WHEN** the callback arrives with a valid `code` and a known pending `state`
- **THEN** an active connection is created with the `session_id` and `valid_until` returned by Enable Banking
- **AND** every account in the session is linked to the connection with its Enable Banking `uid`
- **AND** the pending authorization is deleted and the response is 303 to `/bancos?connected=1`

#### Scenario: The response does not wait for the first sync
- **WHEN** the callback creates a connection
- **THEN** the response is 303 to `/bancos?connected=1` before Enable Banking is asked for any transaction
- **AND** afterwards the first sync stores the connection's transactions and sets its `last_synced_at`

#### Scenario: The bank returns an error or data is missing
- **WHEN** the callback carries `error`, has no `code`, or its `state` matches no pending authorization
- **THEN** the response is 303 to `/bancos?error=1` and no connection is created

#### Scenario: Session creation fails
- **WHEN** Enable Banking rejects the `code`
- **THEN** the response is 303 to `/bancos?error=1` and no connection is created

#### Scenario: The first sync fails
- **WHEN** the connection is created but the first sync raises an error
- **THEN** the error is logged and the response is still 303 to `/bancos?connected=1`
