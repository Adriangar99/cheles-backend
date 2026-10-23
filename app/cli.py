"""Command-line entry points.

- create-user: creates (or replaces) the app's single user and prints the 2FA QR code.
  docker compose run --rm api python -m app.cli create-user <username>
- migrate: brings the database schema to the latest migration (run on every container start).
"""

import sys

from app import bootstrap
from app.migrate import migrate


def create_user(username: str) -> None:
    migrate()
    bootstrap.create_user(username)


USAGE = "Uso: python -m app.cli create-user <usuario> | python -m app.cli migrate"

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "migrate":
        migrate()
    elif len(sys.argv) == 3 and sys.argv[1] == "create-user":
        create_user(sys.argv[2])
    else:
        sys.exit(USAGE)
