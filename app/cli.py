"""Command-line entry points.

- create-user: creates (or replaces) the app's single user and prints the 2FA QR code.
  docker compose run --rm api python -m app.cli create-user <username>
- migrate: brings the database schema to the latest migration (run on every container start).
"""

import getpass
import io
import sys

import pyotp
import qrcode
from sqlalchemy import delete

from app.db import SessionLocal
from app.migrate import migrate
from app.models import LoginSession, User
from app.security import hash_password


def create_user(username: str) -> None:
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if len(password) < 12:
        sys.exit("Demasiado corta.")
    if password != getpass.getpass("Repite la contraseña: "):
        sys.exit("No coinciden.")

    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Cheles")

    migrate()
    with SessionLocal() as db:
        db.execute(delete(LoginSession))
        db.execute(delete(User))
        db.add(User(username=username, password_hash=hash_password(password), totp_secret=secret))
        db.commit()

    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    out = io.StringIO()
    qr.print_ascii(out=out, invert=True)
    print(out.getvalue())
    print("Escanea el QR con tu app de autenticación (o Contraseñas de iOS).")
    print(f"Clave manual: {secret}")


USAGE = "Uso: python -m app.cli create-user <usuario> | python -m app.cli migrate"

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "migrate":
        migrate()
    elif len(sys.argv) == 3 and sys.argv[1] == "create-user":
        create_user(sys.argv[2])
    else:
        sys.exit(USAGE)
