# Setup

How to install and configure the Cheles API on a Mac. The web app is in
[cheles-frontend](https://github.com/Adriangar99/cheles-frontend) (its [setup](https://github.com/Adriangar99/cheles-frontend/blob/main/docs/setup.md)
covers the rest).

## Prerequisites

- A Docker engine: [OrbStack](https://orbstack.dev) (used while developing Cheles) or Docker Desktop.
- `openssl` (preinstalled on macOS) to create the Enable Banking key pair.
- For development only: [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by uv).

## 1. Settings (`.env`)

    cp .env.example .env

Docker Compose reads `.env`; the API container receives the settings below. `.env` is never committed.

| Setting | Default | What it is |
| --- | --- | --- |
| `DB_PASSWORD` | *required* | Password of the Postgres user `cheles`; Compose builds `DATABASE_URL` from it. |
| `DATABASE_URL` | *required outside Compose* | `postgresql+psycopg://cheles:<password>@<host>:5432/cheles`. The API refuses to start without it. |
| `PUBLIC_URL` | `http://localhost:3000` | URL of the web app. The bank sends the browser back to `<PUBLIC_URL>/api/banks/callback`. |
| `COOKIE_SECURE` | `false` | Mark the session cookie `Secure`; set to `true` only when the web app is served over HTTPS. |
| `SESSION_DAYS` | `14` | Days a login session lasts. |
| `EB_APPLICATION_ID` | *empty* | Enable Banking application ID (step 2). Without it, bank actions answer «Enable Banking no está configurado». |
| `EB_PRIVATE_KEY_PATH` | `/run/secrets/eb_private_key` | Where the container finds the private key; Compose mounts `secrets/eb_private_key.pem` there. |
| `EB_API_URL` | `https://api.enablebanking.com` | Enable Banking API. |
| `EB_COUNTRY` | `ES` | Default country when listing and connecting banks. |
| `EB_CONSENT_DAYS` | `180` | Days of access requested from the bank on each authorization. |
| `SYNC_HOURS` | `7,19` | Hours of the automatic sync, comma-separated, Europe/Madrid. |
| `INITIAL_HISTORY_DAYS` | `730` | How far back the first read of an account goes (banks may return less). |

## 2. Enable Banking (once)

Cheles reads your accounts through [Enable Banking](https://enablebanking.com). In restricted mode (free) an
application can only access accounts you link yourself, which is exactly the single-user case.

1. **Create the key pair** in `secrets/` (git-ignored; the private key never leaves your Mac):

       mkdir -p secrets
       openssl req -new -newkey rsa:4096 -nodes -x509 -days 3650 \
         -subj "/CN=cheles" -keyout secrets/eb_private_key.pem -out secrets/eb_certificate.pem
       chmod 600 secrets/eb_private_key.pem

   The API signs its requests to Enable Banking with the private key (RS256 JWT); Enable Banking checks them with the
   certificate.
2. **Register an application** at <https://enablebanking.com/cp/applications>:
   - upload `secrets/eb_certificate.pem` (only the certificate, never the private key);
   - allowed redirect URL: `http://localhost:3000/api/banks/callback`, i.e. `<PUBLIC_URL>/api/banks/callback`;
   - copy the **Application ID** into `EB_APPLICATION_ID` in `.env`.
3. **Link your accounts** in the Enable Banking dashboard (restricted mode), then restart the API:
   `docker compose up -d`.

On OrbStack and Docker Desktop the container user can read the `600` key file mounted by Compose. On a Linux Docker
host the file must be readable by the container's user (uid of `cheles` in the image).

## 3. Start

    docker compose up -d --build

This starts Postgres and the API on the Docker networks it creates (`cheles-net` is shared with the web app). The API
publishes no port; schema migrations run on every start. **Start the backend before the frontend.**

Both repos share the Compose project name `cheles`. Never run `docker compose down --remove-orphans` from one repo: it
would also remove the other repo's containers.

## 4. The user

Cheles has a single user, with a password and a 6-digit code from an authenticator app (TOTP):

    docker compose run --rm api python -m app.cli create-user <username>

It asks for the password twice (at least 12 characters) and prints a QR code: scan it with your authenticator app
(Contraseñas on iOS, Google Authenticator, 1Password…). Running it again replaces the user and closes every session.

Then start the web app ([frontend setup](https://github.com/Adriangar99/cheles-frontend/blob/main/docs/setup.md)), open
<http://localhost:3000>, log in, and connect your banks from «bancos».
