# platform/service-runtime Specification

## Purpose

Defines what the backend service needs to start, how it brings the database schema up to date without losing data, and
how its liveness can be checked, so the service can be deployed and restarted safely.

## Requirements

### Requirement: Required database configuration
The service SHALL require `DATABASE_URL` to be set and SHALL refuse to start without it, reporting that the setting is
missing. No default database URL or credentials are built into the code.

#### Scenario: Missing database URL
- **WHEN** the API or the CLI starts without `DATABASE_URL`
- **THEN** it exits with an error naming `DATABASE_URL` and does not attempt any database connection

### Requirement: Schema migrations on startup
Before serving requests, the service SHALL bring the database schema to the latest version: an empty database gets
the full schema, an up-to-date database is left as is, and an older versioned database is upgraded.

#### Scenario: Empty database
- **WHEN** the container starts against an empty database
- **THEN** every table is created at the latest schema version before the API accepts requests

#### Scenario: Database already up to date
- **WHEN** the container restarts against a database at the latest version
- **THEN** no schema change is applied and the data is untouched

### Requirement: Adoption of a pre-migration database
When the database already has the application's tables but no recorded schema version (created before migrations
existed), the service SHALL record it as the baseline version without modifying tables or data, and then apply any
later migrations.

#### Scenario: Existing database created before migrations
- **WHEN** the container starts against a database with the application's tables and rows but no schema version
- **THEN** the database is marked as the baseline version, every existing row is kept and the API starts

### Requirement: Health endpoint
The service SHALL answer `GET /api/health` with `{"ok": true}` without requiring a session.

#### Scenario: Health check
- **WHEN** `GET /api/health` is called without a session cookie
- **THEN** the response is 200 with `{"ok": true}`
