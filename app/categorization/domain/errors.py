class UnknownCategory(Exception):
    pass


class EmptyRulePattern(Exception):
    """A rule pattern that is empty once trimmed would match every transaction."""
