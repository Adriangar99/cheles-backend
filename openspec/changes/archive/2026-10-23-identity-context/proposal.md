# Proposal

## Why

The backend is still a flat package where routes, persistence and rules are mixed (`app/main.py`, `app/security.py`).
With the characterization suite in place we can start the hexagonal migration safely. Identity is the smallest and
most self-contained context, so it is the pilot that establishes the structure, the composition root and the
architecture contracts every later context will follow.

## What Changes

- New `app/identity/` bounded context with `domain/`, `application/` and `infrastructure/` layers:
  - pure domain (dataclasses, no SQLAlchemy/FastAPI/argon2/pyotp): the single user, login sessions and the per-IP
    login attempt limit;
  - application use cases behind ports: log in, log out, authenticate a request, create the single user;
  - infrastructure adapters: SQLAlchemy ORM rows and repositories (same tables, no migration), argon2 password hasher,
    pyotp TOTP verifier, system clock, secure token generator, the FastAPI router for `/api/auth/*`, and the
    `create-user` CLI command.
- A composition root (`app/bootstrap.py`) that wires adapters into use cases; FastAPI and the CLI obtain use cases
  from it instead of building dependencies themselves.
- A public API (`app/identity/public.py`) for code outside the context: the FastAPI dependency that requires an
  authenticated user, used by the remaining legacy routes.
- `import-linter` with contracts: layer order inside identity, pure domain, identity does not import legacy modules,
  and the rest of the code reaches identity only through its public API.
- Removal of the legacy identity code (`app/security.py`, `User`/`LoginSession` in `app/models.py`, auth routes in
  `app/main.py`).
- Characterization tests keep their scenarios; only their imports and fixtures adapt (e.g. the throttle clock is
  replaced through the composition root instead of monkeypatching a module). New unit tests cover the use cases with
  in-memory adapters where they add behavior coverage the HTTP tests cannot reach cheaply.
- No shared kernel and no event bus: identity needs neither; they arrive with the first context that does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a refactor: `identity/user-authentication` keeps every requirement and scenario, so the change sets
`skip_specs: true`.

## Impact

- **Bounded contexts**: identity (migrated). The other contexts stay in the legacy modules and keep working; their
  routes depend on identity only through `app.identity.public`.
- **Cross-context events**: none added or changed.
- **Security surface**: touched in code, not in behavior. Password hashing, TOTP validation, session cookies and the
  login throttle move to new modules; the characterization tests of `identity/user-authentication` must stay green
  unchanged in their assertions.
- **Database**: same tables and columns; the ORM classes move, so `migrations/env.py` imports them from their new
  location. No Alembic migration.
- **Dependencies**: `import-linter` added to the dev group and to CI.

### Out of scope

- Migrating any other context, introducing the shared kernel or the event bus.
- Fixing the observations recorded in `specs-base` (e.g. non-constant-time login, in-memory throttle).
- Moving shared platform modules (`app/config.py`, `app/db.py`, `app/migrate.py`) into a platform package; they stay
  where they are and identity's infrastructure may use them.
