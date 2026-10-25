## MODIFIED Requirements

### Requirement: Manual sync
The system SHALL allow syncing one connection with `POST /api/banks/{id}/sync`, returning `new` (new transactions),
`status` and `error` of the connection, and every active connection with `POST /api/sync`, returning `new`. A
connection that is not `active` is not read: the response reports 0 new transactions and its current status, and
Enable Banking is not called.

#### Scenario: Sync one connection
- **WHEN** an existing connection is synced
- **THEN** the response is `{"new": <n>, "status": <status>, "error": <last error or null>}`

#### Scenario: Unknown connection
- **WHEN** an id that does not exist is synced
- **THEN** the response is 404

#### Scenario: Sync everything
- **WHEN** `POST /api/sync` is called
- **THEN** every `active` connection is synced and the response is `{"new": <total new transactions>}`

#### Scenario: Syncing an expired connection
- **WHEN** a connection with status `expired` but a future `valid_until` is synced
- **THEN** the response is `{"new": 0, "status": "expired", "error": <last error or null>}`, Enable Banking is not
  called and `last_synced_at` is not updated
