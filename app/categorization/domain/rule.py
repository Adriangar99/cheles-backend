from dataclasses import dataclass

DEFAULT_RULE_PRIORITY = 100
# User rules win over the default catalog
USER_RULE_PRIORITY = 10


@dataclass
class Rule:
    """A movement whose « counterparty description » text contains `pattern` gets `category_id`."""

    pattern: str
    category_id: int
    priority: int = DEFAULT_RULE_PRIORITY
    id: int | None = None
