## ADDED Requirements

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
