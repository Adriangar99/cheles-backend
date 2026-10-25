# Design

## Context

See proposal.md. Current README sections: getting started, architecture, development (API contract, database and
migrations), Enable Banking setup (5 lines, no key generation), account roles, security, language, OpenSpec.

## Goals / Non-Goals

**Goals:** a newcomer can install, configure Enable Banking and run Cheles from the docs alone; each topic has one home.

**Non-Goals:** user manual of the screens (frontend docs); API reference (the OpenAPI contract is the reference).

## Decisions

- **English**, like all documentation; quoted UI literals stay in Spanish.
- **One home per topic**: README links, never duplicates; specs remain the source of truth for behavior and
  `features.md` summarizes and links them.
- **Commands are verified**: every command in `setup.md`, `development.md` and `operations.md` is run once on this
  machine (the `openssl` key generation in a scratch directory; backup and restore against a throwaway database) before
  the change is marked done.
- **Settings table generated from `Settings`** by reading `app/config.py` (names, defaults, required), checked by eye
  against the code; no generator is added.
- **No new tooling** (no docs site, no link checker in CI); relative links are checked once with a small script during
  the change.

## Risks / Trade-offs

- [Docs drift from the code] → Behavior lives in specs; docs link to them. Settings and commands are the parts that
  can drift; the review checklist of later changes includes the docs.

## Migration Plan

Docs only.
