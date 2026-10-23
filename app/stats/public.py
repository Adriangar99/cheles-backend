"""The stats API available to the rest of the app; everything else in app.stats is internal."""

from app.stats.application.use_cases import StatsServices

__all__ = ["StatsServices"]
