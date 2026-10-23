"""The identity API available to the rest of the app; everything else in app.identity is internal."""

from app.identity.domain.user import User as AuthenticatedUser
from app.identity.infrastructure.http import require_user

__all__ = ["AuthenticatedUser", "require_user"]
