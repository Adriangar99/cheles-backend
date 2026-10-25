# Operations

Day-to-day running of the Cheles API with Docker Compose. Commands run from the backend repo.

## Sync

The API reads every active connection at `SYNC_HOURS` (7:00 and 19:00, Europe/Madrid, by default) and on demand from
«bancos» («leer ahora»). Each read stores new transactions, refreshes the balance and records any provider error on
the connection. A failed scheduled sync is logged; the API keeps running.

## Logs

    docker compose logs -f api            # API, migrations on start, scheduled sync
    docker compose logs -f db

## Backups

The database lives in the Compose volume `cheles_db-data`. Back it up with `pg_dump` (custom format) into `backups/`, which is
git-ignored:

    mkdir -p backups
    docker compose exec -T db pg_dump -U cheles -d cheles --format=custom > backups/cheles-$(date +%F).dump

Restore a backup over the current database (it drops and recreates every object first):

    docker compose exec -T db pg_restore -U cheles -d cheles --clean --if-exists < backups/cheles-YYYY-MM-DD.dump

Keep backups outside the Mac as well: they contain your transactions.

## Updating

    git pull
    docker compose up -d --build

Migrations run when the API container starts (`python -m app.cli migrate`). Back up first when a release adds a
migration (`migrations/versions/`).

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| «hay que reconectar» on a bank | The consent expired (180 days) or the bank revoked it. Tap «reconectar» and authorize again; accounts and history are kept. |
| «Enable Banking no está configurado» | `EB_APPLICATION_ID` is empty or `secrets/eb_private_key.pem` is missing or unreadable. See [setup](setup.md#2-enable-banking-once), then `docker compose up -d`. |
| «Enable Banking: …» | Enable Banking rejected the request; the text after the colon is its answer. Check the application and its linked accounts in the Enable Banking dashboard. |
| «Demasiados intentos, espera unos minutos» | 5 failed logins from your IP within 15 minutes. Wait, or restart the API (`docker compose restart api`), which clears the counter. |
| Lost access to the authenticator | Create the user again: `docker compose run --rm api python -m app.cli create-user <username>` (closes every session; data is kept). |
| Figures leave out an amount | Only euros are counted; «mi mes» names the other currencies it left out. |
| Many unused Docker volumes | The test suite's throwaway Postgres (testcontainers) leaves anonymous volumes. With the stack running (so `cheles_db-data` is in use), list them with `docker volume ls -qf dangling=true` and remove the ones you recognize with `docker volume rm <id>`. Never remove or prune `cheles_db-data`: it is the database. |
