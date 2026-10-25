# Proposal

## Why

Block 3 of the roadmap: the README mixes setup, architecture and conventions in one page, and some things a new
install needs are missing or only implied: how to create the Enable Banking key pair (`.pem`), what every setting does,
how to back up the database, what to do when a consent expires or the provider is not configured. The user wants a
README that explains what the project does and links to focused documents.

## What Changes

- `README.md` becomes a short entry point: what Cheles is, the features in a few lines, a quick start, and links.
- New `docs/`:
  - `features.md`: what the API does, by bounded context, linking to each spec.
  - `setup.md`: prerequisites; `.env` settings table (every `Settings` field, required or default); Enable Banking step
    by step, including generating the private key and certificate with `openssl`, registering the application and the
    redirect URL, and linking accounts in restricted mode; first user and authenticator app; start order with the
    frontend.
  - `architecture.md`: bounded contexts, hexagonal layout, ports, events, read models, composition root, the
    import-linter contracts.
  - `development.md`: uv commands, tests and coverage, characterization tests and the spec-coverage meta-test,
    mutation checks, the API contract, migrations, CI, the OpenSpec workflow.
  - `operations.md`: scheduled sync, logs, backups and restore with `pg_dump`/`psql`, updating (migrations on start),
    troubleshooting (consent expired, «Enable Banking no está configurado», a login blocked by too many attempts,
    orphaned Docker volumes from tests).
- `app/config.py` comments translated to English (the project convention), no behavior change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs: true`): documentation only.

## Impact

- **Code**: comments in `app/config.py` only.
- **Security surface**: none; the docs repeat that `.env` and `secrets/` are never committed and that the private key
  never leaves the Mac.

### Out of scope

- The frontend docs (separate change in cheles-frontend, linked from here).
