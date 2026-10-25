## MODIFIED Requirements

### Requirement: Login with password and TOTP code
The system SHALL accept a login (`POST /api/auth/login` with `username`, `password` and `code`) only when the user
exists, the password is correct and the TOTP code is valid. Codes from the current period and one adjacent period are
accepted, ignoring surrounding whitespace. Every failure returns the same response, without revealing what failed,
and does the same work: the password is always hashed and the code always checked, whether the user exists or not.

#### Scenario: Successful login
- **WHEN** a valid username, password and TOTP code are sent
- **THEN** the response is 200 with `{"ok": true}` and a session cookie

#### Scenario: TOTP code from the previous period
- **WHEN** the code belongs to the 30-second period right before the current one
- **THEN** the login is accepted

#### Scenario: Any wrong credential
- **WHEN** the user does not exist, the password is wrong or the TOTP code is invalid
- **THEN** the response is 401 with detail «Datos incorrectos» in all three cases

#### Scenario: Same work for every failure
- **WHEN** a login is attempted with an unknown user, and then with a known user and a wrong password
- **THEN** both attempts verify one password hash and one TOTP code
