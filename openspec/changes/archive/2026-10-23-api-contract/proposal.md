# Proposal

## Why

The frontend is about to generate its API types from the backend's OpenAPI document, but every route declares
`response_model=None` (to keep FastAPI's number serialization), so the document describes requests and no responses.
Generated types would then cover only half the contract, and response shapes would stay hand-written in the frontend,
free to drift. This change makes the OpenAPI document a complete, versioned contract without changing any JSON the
API returns.

## What Changes

- Every JSON route declares a Pydantic response model (16 routes; the bank callback keeps returning a redirect and
  `/api/health` gets a trivial model too). Models live in each context's `infrastructure/http.py` (and `app/main.py`
  for the composition-edge routes).
- `app/http_types.py` provides the annotated types that keep today's JSON exactly: `JsonDecimal` (encoded like
  FastAPI's `decimal_encoder`: integer when the value has no fractional exponent, float otherwise) and `JsonDateTime`
  (`isoformat()`, so UTC stays `+00:00`), both documented as number / date-time in the schema.
- `python -m app.cli openapi` writes the OpenAPI document to the versioned `openapi.json` at the repo root (sorted keys,
  stable formatting). A test fails when `openapi.json` differs from what the app generates, so the contract cannot
  drift unnoticed.
- README documents how to regenerate the contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs: true`): responses keep their current shape and values; the change only declares them.

## Impact

- **Bounded contexts**: every context's HTTP adapter (identity, categorization, transactions, banking, stats) and the
  composition edge (`app/main.py`). Domain and application layers are untouched.
- **Cross-context events**: none.
- **Security surface**: none. The OpenAPI document stays unpublished at runtime (`openapi_url=None`); it is only
  generated offline and versioned in the repository.
- **Consumers**: cheles-frontend will copy `openapi.json` and generate its types from it (frontend change).

### Out of scope

- Publishing `/openapi.json` or docs at runtime.
- Changing any response shape, naming or status code.
- The frontend side (its own change).
