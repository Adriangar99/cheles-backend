"""Command-line entry points.

- create-user: creates (or replaces) the app's single user and prints the 2FA QR code.
  docker compose run --rm api python -m app.cli create-user <username>
- migrate: brings the database schema to the latest migration (run on every container start).
- openapi: writes the API contract to openapi.json (versioned; cheles-frontend generates its types from it).
"""

import json
import sys
from pathlib import Path

from app import bootstrap
from app.migrate import migrate


def create_user(username: str) -> None:
    migrate()
    bootstrap.create_user(username)


def export_openapi() -> Path:
    from app.main import app  # imported here: only this command needs the whole web app

    path = Path(__file__).resolve().parents[1] / "openapi.json"
    path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


USAGE = "Uso: python -m app.cli create-user <usuario> | python -m app.cli migrate | python -m app.cli openapi"

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "migrate":
        migrate()
    elif len(sys.argv) == 2 and sys.argv[1] == "openapi":
        print(f"Written {export_openapi()}")
    elif len(sys.argv) == 3 and sys.argv[1] == "create-user":
        create_user(sys.argv[2])
    else:
        sys.exit(USAGE)
