# Tasks

TDD note: this is a refactor. The safety net is the existing `identity/user-authentication` characterization suite,
which must stay green after every task. New unit tests are written first only for the pure policy and orchestration
listed in design.md (throttle, `LogIn` order); moved code without new logic is covered by the characterization tests.

## 1. Architecture contracts

- [x] 1.1 Add `import-linter` to the dev group, create the empty `app/identity/{domain,application,infrastructure}` packages and `app/identity/public.py`, and configure the four contracts from design.md in `pyproject.toml`; verify `uv run lint-imports` passes
- [x] 1.2 Add a `lint-imports` step to `.github/workflows/ci.yml` and the command to the README development section; verify a deliberate forbidden import (e.g. `import sqlalchemy` in `app/identity/domain`) makes `lint-imports` fail, then remove it

## 2. Domain

- [x] 2.1 Write failing unit tests for `LoginThrottle` (blocks at 5 failures within 900 s, a failure older than the window stops counting, reset clears the key, keys are independent), then implement `app/identity/domain/throttle.py` with time passed in; verify the tests pass
- [x] 2.2 Add `User`, `LoginSession` (`is_active`), `SessionToken` (`hashed()`), `ensure_valid_password` and the domain errors; verify `uv run mypy` and `uv run lint-imports` pass

## 3. Application

- [ ] 3.1 Define the ports in `app/identity/application/ports.py` (repositories, unit of work, password hasher, TOTP service, clock, token generator); verify `uv run mypy` passes
- [ ] 3.2 Write failing unit tests for `LogIn` with in-memory adapters (throttle checked before credentials; wrong credentials record a failure and raise `InvalidCredentials`; success resets the throttle, purges expired sessions and stores the hashed token with expiry now + session_days), then implement `LogIn`; verify the tests pass
- [ ] 3.3 Implement `LogOut`, `Authenticate` and `CreateUser` (deletes every session and user before adding the new one; enforces the password minimum); verify `uv run mypy` and `uv run lint-imports` pass

## 4. Infrastructure and composition root

- [ ] 4.1 Move `User`/`LoginSession` from `app/models.py` to `UserRow`/`LoginSessionRow` in `app/identity/infrastructure/orm.py` (same tables), add the repositories and `SqlUnitOfWork`, and import the module in `migrations/env.py`; verify `uv run alembic check` against a migrated scratch database reports no changes
- [ ] 4.2 Add the security adapters (argon2, pyotp ±1 period, system clock, `secrets.token_urlsafe(32)`), the FastAPI router with the `identity_services` placeholder and `require_user`, the CLI `create_user_command`, and `public.py`; verify `uv run mypy` and `uv run lint-imports` pass
- [ ] 4.3 Add `app/bootstrap.py` (`Container`, `wire(app, container)`), switch `app/main.py` to `wire()` + `require_user` and `app/cli.py` to the identity command, and delete `app/security.py` plus the legacy auth routes; adapt the characterization tests' imports and fixtures (fresh container per test, throttle clock via the container, user creation via `CreateUser`) without changing any assertion; verify the whole suite passes, `git diff tests/` shows no changed assertions, and ruff, mypy and lint-imports pass

## 5. Documentation and verification

- [ ] 5.1 Add an "Architecture" section to `README.md` describing the context layout, the composition root and the import contracts, using identity as the reference; verify the paths it names exist
- [ ] 5.2 Run `docker compose up -d --build`; verify the API starts, `http://127.0.0.1:3000/api/auth/me` returns 401 «No autenticado» through the web app, and CI passes on the pull request

## Workflow follow-up

- Archive the change (`/opsx:archive`; no spec sync since `skip_specs: true`).
- Next change: migrate `categorization` (introducing the shared kernel and the event bus when its rule-created → reprocess flow needs them).
