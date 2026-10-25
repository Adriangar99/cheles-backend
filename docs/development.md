# Development

Requires [uv](https://docs.astral.sh/uv/) and a Docker engine (the tests start a throwaway Postgres with
testcontainers).

## Commands

    uv sync                              # Python 3.12 + runtime and dev dependencies from uv.lock
    uv run pytest --cov                  # tests + coverage (fails below the ratchet in pyproject.toml, 97 %)
    uv run ruff check . && uv run ruff format --check .
    uv run mypy                          # strict, over app/, migrations/ and tests/
    uv run lint-imports                  # architecture contracts

CI (GitHub Actions) runs the same checks on every pull request and on `main`.

## Tests

- **One test per spec scenario.** Each scenario in `openspec/specs/<context>/<capability>/spec.md` has a test in
  `tests/<context>/test_<capability>.py` whose docstring starts with `Scenario: <title>`
  (`Scenarios: <a>, <b>` for a parametrized test); `tests/test_spec_coverage.py` fails when one is missing.
- **Tests first.** A new or changed scenario gets its test before the code, and the test must fail for the right reason.
- **Through the API, against Postgres.** Most tests use the FastAPI client with the fake Enable Banking provider
  (`tests/fakes.py`) and assert responses or stored rows (`tests/helpers.stored_row`); pure domain rules have unit tests
  next to them.
- **Mutation checks.** After committing, break the code on purpose (a condition, a constant, a mapping) and check a test
  fails; a surviving mutant means a missing test or a dead branch.
- **No ceremonial tests**: no tests of test helpers, one-off checks or trivial code.

## API contract

`openapi.json` (versioned) is the API contract; cheles-frontend generates its TypeScript types from a copy of it.
After changing a route or a response model, regenerate and commit it (no database connection is made):

    DATABASE_URL=postgresql+psycopg://unused@localhost/unused uv run python -m app.cli openapi

`tests/platform/test_api_contract.py` fails while the file is out of date. Response models use the field types in
`app/http_types.py` so amounts stay JSON numbers and datetimes keep their `+00:00` offset.

## Database and migrations

The schema is managed with Alembic; the container runs `python -m app.cli migrate` before starting the API.

    export DATABASE_URL=postgresql+psycopg://cheles:<password>@localhost:5432/cheles   # a database at the latest revision
    uv run alembic revision --autogenerate -m "describe the change"                     # review the generated file
    uv run python -m app.cli migrate                                                    # apply it

## Workflow

Changes are planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec) (`openspec/`) and the Claude Code commands
`/opsx:propose` → `/opsx:apply` → pull request → `/opsx:archive` (which merges the change's delta specs into
`openspec/specs/`). Work happens on branches, never on `main`. Code, specs and documentation are in English; the app's
user-facing copy is Spanish (Spain).
