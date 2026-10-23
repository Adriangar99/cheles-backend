class IdentityError(Exception):
    """Base class for identity rule violations; adapters translate them into HTTP or CLI responses."""


class InvalidCredentials(IdentityError):
    """Unknown user, wrong password or wrong TOTP code (deliberately indistinguishable)."""


class TooManyAttempts(IdentityError):
    """The client exceeded the login attempt limit."""


class NotAuthenticated(IdentityError):
    """No session, or the session is unknown or expired."""


class PasswordTooShort(IdentityError):
    pass
