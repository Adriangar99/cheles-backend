# Architecture

Domain-driven design with a hexagonal architecture per bounded context: `identity`, `categorization`, `transactions`,
`banking` and `stats`. FastAPI + SQLAlchemy 2 + Postgres; Python 3.12, managed with uv.

## Layout

    app/<context>/
      domain/           # entities, value objects and rules; plain Python, no frameworks
      application/      # use cases and the ports (Protocols) they depend on
      infrastructure/   # adapters: SQLAlchemy rows and repositories, FastAPI router, Enable Banking client, CLI…
      public.py         # the only part of the context the rest of the app may import
    app/shared/         # shared kernel: Money, YearMonth, typed ids, literals, event bus
    app/bootstrap.py    # composition root: builds adapters, binds use cases, wires FastAPI dependencies and events
    app/main.py         # composition edge: app creation, startup (catalog seeding, scheduled sync), cross-context routes
    app/orm_registry.py # every context's ORM rows, for Alembic

## Rules

- Domain entities are dataclasses; ORM rows live in `infrastructure/orm.py` and repositories translate between them
  (stored literals are parsed and checked, never cast).
- FastAPI routes depend on placeholder providers that `bootstrap.wire(app, container)` overrides, so tests can wire
  their own `Container` (fake clock, fake Enable Banking provider, spies).
- **Contexts never import each other's internals.** When a context needs data it does not own (own IBANs, account
  names, category suggestions, where to store synced transactions) it declares a port, and the composition root plugs
  in an adapter over the owner's public API.
- **Flows that must answer the caller are orchestrated at the edge** (`POST /api/rules`: create the rule in
  categorization, then reprocess in transactions).
- **Reactions go through the in-memory event bus** (`app/shared/events.py`): publishers publish after their unit of work
  commits; handlers run synchronously in their own transaction; a failing handler is logged without undoing the
  publisher's change. Today: `AccountIbanChanged` → transactions reprocess.
- **Stats owns no tables**: it reads the read models other contexts publish (transactions' movement records, banking's
  account snapshots, categorization's labels) through its own ports and aggregates them in its pure domain.

## Enforcement

`uv run lint-imports` checks the contracts in `pyproject.toml` (`[tool.importlinter]`):

- layers only depend downwards inside a context, and domain/application import no frameworks;
- each context, and the composition edge, reach other contexts only through their `public.py`;
- the shared kernel depends on nothing else in the app.

`app/bootstrap.py` is the only module that wires internals together.
