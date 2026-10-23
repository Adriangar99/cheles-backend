# Design

## Context

See proposal.md. Today every route returns a `dict` with `response_model=None`, so FastAPI encodes with
`jsonable_encoder`: `Decimal("-12.50") → -12.5`, `Decimal("0") → 0`, `datetime(…, UTC) → "2026-10-23T12:00:00+00:00"`,
`date → "2026-10-03"`. With a Pydantic response model and default settings the same values would become `"-12.50"`
and `"2026-10-23T12:00:00Z"` (checked), which would break the frontend and the characterization tests.

## Goals / Non-Goals

**Goals:** a complete OpenAPI contract (requests and responses) in a versioned file; identical JSON on the wire.

**Non-Goals:** runtime docs, response redesign.

## Decisions

### Serialization-preserving annotated types (`app/http_types.py`)
- `JsonDecimal = Annotated[Decimal, PlainSerializer(encode_decimal, return_type=float), WithJsonSchema({"type":
  "number"})]`, where `encode_decimal` mirrors `fastapi.encoders.decimal_encoder` (int if the exponent is ≥ 0, float
  otherwise).
- `JsonDateTime = Annotated[datetime, PlainSerializer(datetime.isoformat, return_type=str), WithJsonSchema({"type":
  "string", "format": "date-time"})]`.
- Dates use plain `date` (Pydantic and `jsonable_encoder` agree).
- The module sits outside the contexts, next to `app/config.py` and `app/db.py`, because it is HTTP plumbing shared by
  every adapter; contexts' domain/application layers still never import Pydantic (contract unchanged).

### Response models next to their routes
Each `infrastructure/http.py` declares small `BaseModel`s mirroring the dicts it returns today (same keys, same
nullability, `Literal` types where the value set is closed: roles, kinds, connection status, category kind). Routes set
`response_model=<Model>` and keep returning the same dicts, so FastAPI validates and serializes them through the
models. Lists use `list[Model]`; the balances map uses `dict[str, JsonDecimal]`.

### Contract file and drift test
- `app/cli.py` gains `openapi`: writes `json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False)` plus a
  trailing newline to `openapi.json`.
- `tests/platform/test_api_contract.py` compares the parsed file with `app.openapi()` and fails with a hint to run the
  command. It guards a real artifact other repos consume, unlike one-off checks.

### Tests
The characterization suite is the guard for identical JSON: it asserts amounts as numbers (a string would fail) and
datetimes with `+00:00`. No other new tests: integer-vs-float encoding is invisible to JSON consumers and is kept only
for parity.

## Risks / Trade-offs

- [A model forgets a field the frontend reads] → Validation would drop unknown keys silently; the characterization
  tests compare whole objects for every representation scenario, so a missing key fails them.
- [Response validation cost] → Negligible at this volume.

## Migration Plan

Refactor only; rebuild the image. The new `openapi.json` is consumed by the frontend in its next change.
