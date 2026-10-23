# Cheles · backend

Cheles API (working name): FastAPI + Postgres. Password + TOTP login, sync with Enable Banking and statistics. The
frontend lives in [cheles-frontend](https://github.com/Adriangar99/cheles-frontend).

Transactions are stored exactly as the bank returns them (`raw`), so they can be reprocessed without fetching them
again.

## Getting started

    cp .env.example .env                 # and fill in DB_PASSWORD, EB_APPLICATION_ID…
    docker compose up -d --build
    docker compose run --rm api python -m app.cli create-user <username>   # password + 2FA QR code

The API publishes no ports: it is only exposed to the web app through the Docker network `cheles-net`, which this
compose file creates (alias `api`, port 8000). **Always start the backend first**, then the frontend.

Both repos share the Compose project name `cheles`, so `api`, `db` and `web` show up together. Never run
`docker compose down --remove-orphans` from one repo: it would also remove the other repo's containers.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Docker (the tests start a throwaway Postgres with testcontainers).

    uv sync                              # Python 3.12 + runtime and dev dependencies from uv.lock
    uv run pytest --cov                  # tests + coverage (fails below the ratchet in pyproject.toml)
    uv run ruff check . && uv run ruff format --check .
    uv run mypy                          # strict, over app/, migrations/ and tests/

CI (GitHub Actions) runs the same checks on every pull request and on `main`.

Every scenario in `openspec/specs/` has a test whose docstring quotes it (`tests/<context>/test_<capability>.py`);
`tests/test_spec_coverage.py` fails when one is missing.

### Database and migrations

`DATABASE_URL` is required (Docker Compose builds it from `DB_PASSWORD`). The schema is managed with Alembic: the
container runs `python -m app.cli migrate` before starting the API, which also adopts a database created before
migrations existed.

    export DATABASE_URL=postgresql+psycopg://cheles:<password>@localhost:5432/cheles   # a database at the latest revision
    uv run alembic revision --autogenerate -m "describe the change"                     # review the generated file
    uv run python -m app.cli migrate                                                    # apply it

## Enable Banking setup (once)

1. Go to https://enablebanking.com/cp/applications and create an application.
2. Upload `secrets/eb_certificate.pem`; the private key `secrets/eb_private_key.pem` never leaves your Mac.
3. Redirect URL: `http://localhost:3000/api/banks/callback` (must match `PUBLIC_URL` in `.env`).
4. Copy the **Application ID** into `EB_APPLICATION_ID` in `.env` and restart: `docker compose up -d`.
5. Restricted mode (free): link your own accounts from the dashboard.

## Account roles

`main` (day to day: salary and payments), `savings`, `excluded` (does not count). Transfers between your own accounts
(detected by IBAN) count as neither expense nor income. Any transaction can be marked by hand with ⇄.

## Security

Neither the API nor the database is published; the database sits on an internal network the web app cannot see.
Session via `HttpOnly` cookie; at most 5 login attempts per IP; `secrets/` and `.env` are kept out of git.

## Language

Code, specs and documentation are written in English. The app's user-facing copy is Spanish (Spain).

## Development with OpenSpec

Changes are planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec) (`openspec/`), using the Claude Code
commands `/opsx:explore`, `/opsx:propose`, `/opsx:update`, `/opsx:apply`, `/opsx:sync` and `/opsx:archive`. Current
behavior is specified under `openspec/specs/`, grouped by bounded context.
