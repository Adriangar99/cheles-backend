"""Terminal adapter for creating the app's single user."""

import getpass
import io
import sys

import qrcode

from app.identity.application.use_cases import CreateUser
from app.identity.domain.errors import PasswordTooShort
from app.identity.domain.user import MIN_PASSWORD_LENGTH, ensure_valid_password


def create_user_command(username: str, create_user: CreateUser) -> None:
    password = getpass.getpass(f"Contraseña (mínimo {MIN_PASSWORD_LENGTH} caracteres): ")
    try:
        ensure_valid_password(password)
    except PasswordTooShort:
        sys.exit("Demasiado corta.")
    if password != getpass.getpass("Repite la contraseña: "):
        sys.exit("No coinciden.")

    provisioning = create_user(username, password)

    qr = qrcode.QRCode(border=1)
    qr.add_data(provisioning.uri)
    out = io.StringIO()
    qr.print_ascii(out=out, invert=True)
    print(out.getvalue())
    print("Escanea el QR con tu app de autenticación (o Contraseñas de iOS).")
    print(f"Clave manual: {provisioning.secret}")
