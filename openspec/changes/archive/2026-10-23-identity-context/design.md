# Design

## Context

See proposal.md for motivation. Today identity lives in:

- `app/security.py`: argon2 hashing, TOTP check (pyotp, ±1 period), session creation/destruction (SHA-256 token
  hash, expired-session purge), `current_user` FastAPI dependency, and the module-level `LoginThrottle` (5 failures /
  900 s per IP, `time.monotonic`).
- `app/models.py`: `User` and `LoginSession` ORM classes (tables `users`, `login_sessions`).
- `app/main.py`: `/api/auth/login`, `/logout`, `/me` routes, and every other route depends on `current_user`.
- `app/cli.py`: `create-user` (password prompts, 12-char minimum, replaces the user and all sessions, prints QR).

The characterization tests reach this code through HTTP and the CLI, but also import `app.security`
(`login_throttle`, `hash_password`, `time`) and `app.models` (`User`, `LoginSession`) for arrange/assert steps.

## Goals / Non-Goals

**Goals:**
- A reference implementation of the layering every context will copy: pure domain, use cases behind ports,
  adapters at the edge, wiring in one composition root, contracts enforced by import-linter.
- Identical observable behavior: same endpoints, status codes, messages, cookie attributes, CLI prompts and output.

**Non-Goals:**
- Shared kernel, event bus, unit-of-work event collection (no consumer yet).
- Restructuring legacy modules beyond removing what identity takes over.

## Decisions

### Package layout

```
app/
  bootstrap.py                  # composition root: Container + wire(app)
  identity/
    domain/
      user.py                   # User, MIN_PASSWORD_LENGTH, ensure_valid_password()
      session.py                # SessionToken (VO), LoginSession
      throttle.py               # LoginThrottle (pure, time passed in)
      errors.py                 # InvalidCredentials, TooManyAttempts, NotAuthenticated, PasswordTooShort
    application/
      ports.py                  # Protocols: UserRepository, SessionRepository, UnitOfWork, PasswordHasher,
                                #   TotpService, Clock, TokenGenerator
      use_cases.py              # LogIn, LogOut, Authenticate, CreateUser (+ IssuedSession, Provisioning)
    infrastructure/
      orm.py                    # UserRow, LoginSessionRow (same tables)
      repositories.py           # SqlUserRepository, SqlSessionRepository, SqlUnitOfWork
      security.py               # Argon2PasswordHasher, PyotpTotpService, SystemClock, SecretsTokenGenerator
      http.py                   # APIRouter /api/auth/*, identity_services placeholder, require_user
      cli.py                    # create_user_command (getpass, qrcode, prints)
    public.py                   # what the rest of the app may use: require_user, AuthenticatedUser
                                #   (the router and the CLI command are mounted by app/bootstrap.py)
```

`app/config.py`, `app/db.py` and `app/migrate.py` stay as shared platform modules that any infrastructure layer may
use.

### Domain model and value objects
- `User` (id, username, password_hash, totp_secret) and `LoginSession` (token_hash, user_id, expires_at, with
  `is_active(now)`) are plain dataclasses.
- `SessionToken` is an identity-only value object: the opaque cookie value with `hashed()` (SHA-256 hex). It lives in
  identity, not in a shared kernel, because no other context sees session tokens.
- `LoginThrottle` keeps its exact policy (limit 5, window 900 s, failures pruned by age, reset on success) but takes
  the current monotonic time as an argument instead of reading the clock, so it is pure and deterministic.
- The 12-character password minimum moves from the CLI into the domain (`ensure_valid_password`) because it is a rule
  about users, not about the terminal; the «passwords do not match» check stays in the CLI adapter.

### Persistence: pure entities + separate ORM rows
`UserRow`/`LoginSessionRow` keep table names, columns and constraints exactly as today, so there is no migration.
Repositories translate rows ↔ entities. `SqlUnitOfWork` wraps one SQLAlchemy session per request (or CLI run) and
exposes `users`, `sessions` and `commit()`. `migrations/env.py` imports the identity ORM module so
`Base.metadata` stays complete.
*Alternatives* (chosen with the user): imperative mapping, or ORM classes as entities — rejected to keep `domain/`
free of SQLAlchemy.

### Use cases and errors
- `LogIn(username, password, code, client_key) -> IssuedSession(token, expires_at)`: checks the throttle first
  (raises `TooManyAttempts` before looking at credentials), verifies user + password + TOTP in the same
  short-circuit order as today, records a failure and raises `InvalidCredentials`, or resets the throttle, purges
  expired sessions and stores the new session (expiry = now + `session_days`).
- `LogOut(token | None)`, `Authenticate(token | None) -> User` (raises `NotAuthenticated`),
  `CreateUser(username, password) -> Provisioning(secret, uri)` (deletes every session and user, then adds the new
  one).
- The HTTP adapter maps `InvalidCredentials` → 401 «Datos incorrectos», `TooManyAttempts` → 429 «Demasiados
  intentos, espera unos minutos», `NotAuthenticated` → 401 «No autenticado», and owns cookie handling
  (`cheles_session`, HttpOnly, SameSite=Lax, Path=/, Secure from settings). The CLI maps `PasswordTooShort` to
  «Demasiado corta.».

### Dependency injection without import cycles
`identity/infrastructure/http.py` declares a placeholder dependency `identity_services()` that raises if not wired,
and builds `require_user` and the router on top of it. `app/bootstrap.py` creates a `Container` (settings, session
factory, adapters, the single `LoginThrottle` instance, clock) and `wire(app, container)` sets
`app.dependency_overrides[identity_services]` to a per-request provider and includes the router once. `app/main.py`
keeps the legacy routes, depends on `require_user` from `app.identity.public`, and calls `wire()`. `app/cli.py`
runs `migrate()` and then `bootstrap.create_user()`; migrating now happens before the password prompts instead of
after them, which only means a rejected password leaves an already migrated schema (no observable effect).
Tests call `wire()` with a fresh `Container` per test (fresh throttle, optional fake clock), replacing today's
monkeypatching of `app.security`.
*Alternative*: a module-level container imported by the HTTP adapter — rejected, it makes infrastructure depend on
the composition root and creates a cycle.

### Architecture contracts (import-linter, run locally and in CI)
1. **Layers** in `app.identity`: `public` > `infrastructure` > `application` > `domain`.
2. **Pure core**: `app.identity.domain` and `app.identity.application` may not import fastapi, starlette, pydantic,
   sqlalchemy, httpx, argon2, pyotp, qrcode or alembic.
3. **No legacy from identity**: `app.identity` may not import `app.main`, `app.models`, `app.sync`, `app.stats`,
   `app.categorize`, `app.enablebanking` or `app.cli`.
4. **Public API only**: legacy modules may not import `app.identity.domain|application|infrastructure` directly
   (indirect imports through `public` allowed). `app.bootstrap` is exempt as the composition root.

### Tests
- Characterization tests keep every scenario and assertion; only imports and fixtures change (ORM rows from
  `app.identity.infrastructure.orm`, user creation through the `CreateUser` use case, the throttle clock through the
  test container).
- New unit tests (no database) only where they pin behavior the HTTP suite reaches awkwardly: the throttle policy
  (window boundaries) and the `LogIn` orchestration order (throttle before credentials, failure recorded, reset on
  success). No tests for mappers, repositories or adapters: the characterization suite already exercises them.

## Risks / Trade-offs

- [Subtle change in security behavior while moving code] → The identity characterization tests (35 cases) run
  unchanged in their assertions on every task; the CLI, cookie and throttle scenarios are among them.
- [Dependency-override wiring forgotten in some entry point] → The placeholder raises a clear error; the API, the CLI
  and the test fixtures all go through `wire()`/the container, and the health/auth tests would fail immediately.
- [Mapping boilerplate between rows and entities] → Accepted trade-off of the chosen persistence style; kept to two
  small translators.
- [Characterization tests coupled to ORM classes] → They now import identity's ORM rows; when more contexts migrate,
  each test file follows its context the same way.

## Migration Plan

Pure refactor, deployed by rebuilding the image; no data or schema change. Rollback = previous image.
