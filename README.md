# Cheles · backend

Personal finance API for a single user: it reads your bank accounts through [Enable Banking](https://enablebanking.com),
categorizes every transaction, tells transfers between your own accounts apart from real spending, and computes your
monthly figures. FastAPI + Postgres, run with Docker Compose on your Mac. The web app is
[cheles-frontend](https://github.com/Adriangar99/cheles-frontend).

- Password + authenticator-app login, single user, nothing published outside the Docker network.
- Bank connections with 180-day consents, automatic sync twice a day, balances.
- Transactions stored exactly as the bank sends them, so they can be reprocessed; rules, manual categories, notes and
  transfer marks that survive every sync.
- Monthly income, expenses, savings and spending by category, in euros.

## Quick start

    cp .env.example .env                                                   # fill in DB_PASSWORD and EB_APPLICATION_ID
    docker compose up -d --build                                           # Postgres + API (no published ports)
    docker compose run --rm api python -m app.cli create-user <username>   # password + 2FA QR code

Then start the [web app](https://github.com/Adriangar99/cheles-frontend). Enable Banking needs a key pair and an
application first: see [setup](docs/setup.md).

## Documentation

| Document | Contents |
| --- | --- |
| [Setup](docs/setup.md) | Settings, Enable Banking key pair and application, first start, the user |
| [Features](docs/features.md) | What the API does, by bounded context, with links to the specs |
| [Architecture](docs/architecture.md) | Bounded contexts, hexagonal layers, ports, events, enforced boundaries |
| [Development](docs/development.md) | Commands, tests, API contract, migrations, workflow |
| [Operations](docs/operations.md) | Sync, logs, backups, updating, troubleshooting |

Behavior is specified in [`openspec/specs/`](openspec/specs/), grouped by bounded context.

## Security

Neither the API nor the database is published; the database sits on an internal network the web app cannot see. The
session is an `HttpOnly` cookie; at most 5 failed logins per IP in 15 minutes. `.env`, `secrets/` and `backups/` are
never committed, and the Enable Banking private key never leaves your Mac.
