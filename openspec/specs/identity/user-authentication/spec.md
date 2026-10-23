# identity/user-authentication Specification

## Purpose

Ensures that only Cheles' single user can access the API, using a password plus a TOTP second factor, a session held
in an HttpOnly cookie, and protection against repeated login attempts.

## Requirements

### Requirement: Single user creation from the command line
The system SHALL allow creating the user from the CLI (`create-user <username>`), asking for the password twice and
generating a new TOTP secret shown as a QR code and as a manual key. The app has a single user: creating it replaces
the existing user and closes every session.

#### Scenario: Successful creation
- **WHEN** `create-user ana` is run with a password of 12 or more characters entered identically twice
- **THEN** there is exactly one user `ana`, with the password stored as an Argon2 hash and a new TOTP secret
- **AND** the provisioning QR code with issuer `Cheles` and the manual key are printed

#### Scenario: Replaces the previous user
- **WHEN** a user with open sessions already exists and `create-user` is run again
- **THEN** the previous user and every session are deleted before the new user is created

#### Scenario: Password too short
- **WHEN** the password has fewer than 12 characters
- **THEN** the CLI exits with the error «Demasiado corta.» and users and sessions are left untouched

#### Scenario: Passwords do not match
- **WHEN** the repeated password does not match
- **THEN** the CLI exits with the error «No coinciden.» and users and sessions are left untouched

### Requirement: Login with password and TOTP code
The system SHALL accept a login (`POST /api/auth/login` with `username`, `password` and `code`) only when the user
exists, the password is correct and the TOTP code is valid. Codes from the current period and one adjacent period are
accepted, ignoring surrounding whitespace. Every failure returns the same response, without revealing what failed.

#### Scenario: Successful login
- **WHEN** a valid username, password and TOTP code are sent
- **THEN** the response is 200 with `{"ok": true}` and a session cookie

#### Scenario: TOTP code from the previous period
- **WHEN** the code belongs to the 30-second period right before the current one
- **THEN** the login is accepted

#### Scenario: Any wrong credential
- **WHEN** the user does not exist, the password is wrong or the TOTP code is invalid
- **THEN** the response is 401 with detail «Datos incorrectos» in all three cases

### Requirement: HttpOnly cookie session
After a successful login the system SHALL create a 14-day session (configurable) and deliver its token in the
`cheles_session` cookie with `HttpOnly`, `SameSite=Lax`, `Path=/` and `Secure` according to configuration. Only a hash
of the token is stored. Creating a session purges expired sessions.

#### Scenario: Session cookie
- **WHEN** the login succeeds
- **THEN** the `cheles_session` cookie is HttpOnly, SameSite=Lax, Path=/ and expires after 14 days

#### Scenario: The token is not stored in plain text
- **WHEN** a session is created
- **THEN** the database stores the SHA-256 of the token and not the token itself

#### Scenario: Expired sessions are purged
- **WHEN** a new session is created and sessions with a past expiry exist
- **THEN** the expired sessions are deleted

### Requirement: Session-protected endpoints
Every API endpoint except login, logout and health SHALL require a valid, unexpired session. Without one it responds
401 with detail «No autenticado».

#### Scenario: No cookie
- **WHEN** a protected endpoint is called without a session cookie
- **THEN** the response is 401 «No autenticado»

#### Scenario: Expired or unknown session
- **WHEN** the cookie holds an expired token or one that matches no session
- **THEN** the response is 401 «No autenticado»

#### Scenario: Current user
- **WHEN** `GET /api/auth/me` is called with a valid session
- **THEN** the response is `{"username": <username>}`

### Requirement: Logout
The system SHALL allow closing the session with `POST /api/auth/logout`, which deletes the session matching the
cookie's token (if any) and clears the cookie. It does not require authentication.

#### Scenario: Logout with a session
- **WHEN** logging out with a valid session cookie
- **THEN** the session is deleted, the cookie is cleared and the response is `{"ok": true}`
- **AND** that token no longer grants access to protected endpoints

#### Scenario: Logout without a session
- **WHEN** logging out without a cookie
- **THEN** the response is `{"ok": true}`

### Requirement: Per-IP login attempt limit
The system SHALL block logins from an IP that has 5 failed attempts within the last 15 minutes, responding 429 without
checking the credentials. A successful login resets that IP's counter. The counter lives in process memory and is lost
on restart.

#### Scenario: Blocked after 5 failures
- **WHEN** an IP has 5 failed logins within 15 minutes and tries again
- **THEN** the response is 429 «Demasiados intentos, espera unos minutos», even if the credentials are correct

#### Scenario: Sliding window
- **WHEN** more than 15 minutes have passed since a failed attempt
- **THEN** that attempt no longer counts towards the limit

#### Scenario: Reset after a successful login
- **WHEN** an IP with 4 failures logs in successfully
- **THEN** its counter goes back to zero

#### Scenario: Other IPs are not affected
- **WHEN** an IP is blocked
- **THEN** a different IP can still attempt to log in
