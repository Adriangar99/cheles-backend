## ADDED Requirements

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
