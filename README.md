# Cheles · backend

API de Cheles (nombre provisional): FastAPI + Postgres. Login con contraseña + TOTP, sincronización con
Enable Banking y estadísticas. El frontend vive en [cheles-frontend](https://github.com/Adriangar99/cheles-frontend).

Los movimientos se guardan tal cual los da el banco (`raw`), así se puede reprocesar sin volver a pedirlos.

## Arrancar

    cp .env.example .env                 # y rellena DB_PASSWORD, EB_APPLICATION_ID…
    docker compose up -d --build
    docker compose run --rm api python -m app.cli create-user <usuario>   # contraseña + QR del 2FA

La API no publica puertos: se expone solo a la web mediante la red Docker `cheles-net`, que crea este compose
(alias `api`, puerto 8000). Arranca **siempre el backend primero**; luego el frontend.

## Alta en Enable Banking (una vez)

1. Entra en https://enablebanking.com/cp/applications y crea una aplicación.
2. Sube `secrets/eb_certificate.pem`; la clave privada `secrets/eb_private_key.pem` no sale de tu Mac.
3. Redirect URL: `http://localhost:3000/api/banks/callback` (debe coincidir con `PUBLIC_URL` en `.env`).
4. Copia el **Application ID** a `EB_APPLICATION_ID` en `.env` y reinicia: `docker compose up -d`.
5. Modo restringido (gratis): vincula tus propias cuentas desde el panel.

## Roles de cuenta

`día a día` (nómina y pagos), `ahorro`, `no cuenta`. Las transferencias entre tus cuentas (detectadas por IBAN)
no cuentan como gasto ni ingreso. Se puede marcar a mano cualquier movimiento con ⇄.

## Seguridad

La API y la base de datos no se publican; la BD está en una red interna que la web no ve. Sesión con cookie
`HttpOnly`; límite de 5 intentos de login por IP; `secrets/` y `.env` fuera de git.

## Desarrollo con OpenSpec

Cambios planificados con [OpenSpec](https://github.com/Fission-AI/OpenSpec) (`openspec/`), con los comandos
`/opsx:explore`, `/opsx:propose`, `/opsx:update`, `/opsx:apply`, `/opsx:sync` y `/opsx:archive` de Claude Code.
