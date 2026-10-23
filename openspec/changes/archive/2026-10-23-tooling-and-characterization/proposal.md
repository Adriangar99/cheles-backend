# Proposal

## Why

The backend has no tests, no linting, no type checking and no schema migrations, so the hexagonal migration that comes
next would be a refactor without a safety net. This change adds the tooling and a characterization test suite built
from the scenarios in `openspec/specs/`, so every later step can prove that behavior did not change.

## What Changes

- Move dependency management to **uv** with `pyproject.toml` and `uv.lock` (replacing `requirements.txt`); the
  `Dockerfile` installs from the lockfile.
- Add **ruff** (lint + format) and **mypy strict**, and fix every current type error in `app/` (no exclusions).
- Add **pytest + coverage**, with a real Postgres started by **testcontainers**.
- Add **Alembic** with a baseline migration equal to the current schema. The container applies migrations on startup
  and adopts an existing pre-Alembic database without touching its data; `create_all` is removed from the API startup
  and from the CLI.
- Add **characterization tests**: one test per scenario of the backend specs, through the HTTP API (FastAPI test
  client) and the CLI, with Enable Banking replaced by an in-memory fake. Known-defect scenarios are tested as they
  behave today.
- Add **GitHub Actions CI** running ruff, mypy and pytest on pushes to `main` and on pull requests.
- **BREAKING (configuration)**: `DATABASE_URL` becomes mandatory; the hardcoded default URL with credentials is removed
  from `app/config.py`. Docker Compose already sets it, so the deployed app is unaffected.
- Document the development workflow (uv commands, tests, migrations) in the README.

## Capabilities

### New Capabilities

- `platform/service-runtime`: what the service needs to start (required configuration), how the database schema is
  created or upgraded on startup, and the unauthenticated health endpoint.

### Modified Capabilities

None. The characterization tests verify the existing specs without changing their requirements.

## Impact

- **Code**: type annotations and small narrowing fixes in `app/` (no behavior change), `app/config.py`
  (`DATABASE_URL` required), API startup and CLI no longer call `create_all`, a new migration entry point.
- **New files**: `pyproject.toml`, `uv.lock`, `.python-version`, `alembic.ini`, `migrations/`, `tests/`,
  `.github/workflows/ci.yml`. `requirements.txt` is removed.
- **Docker**: image built with uv from the lockfile; the container runs migrations before starting uvicorn.
- **Bounded contexts**: none restructured; tests are grouped by bounded context to mirror the specs and survive the
  migration.
- **Cross-context events**: none added or changed.
- **Security**: touches configuration of secrets. Removing the default database credentials means a missing
  `DATABASE_URL` now fails fast instead of silently connecting with `cheles:cheles`. No ports or auth behavior change.
  CI needs no secrets (tests use a throwaway Postgres and a fake Enable Banking).

### Out of scope

- import-linter and any restructuring into bounded contexts (next change: hexagonal skeleton).
- Fixing the known defects and observations recorded in `specs-base` (separate changes).
- Frontend tooling (its own change in cheles-frontend).
- Tests against the real Enable Banking API.
