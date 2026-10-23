"""Crea (o reemplaza) el único usuario de la app y muestra el QR para el 2FA.

Uso: docker compose run --rm api python -m app.cli create-user <usuario>
"""

import getpass
import io
import sys

import pyotp
import qrcode
from sqlalchemy import delete

from app.db import Base, SessionLocal, engine
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

    Base.metadata.create_all(engine)
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


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "create-user":
        sys.exit("Uso: python -m app.cli create-user <usuario>")
    create_user(sys.argv[2])
