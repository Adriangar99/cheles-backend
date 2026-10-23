from collections.abc import Sequence
from dataclasses import dataclass

from app.categorization.domain.catalog import BIZUM_INCOME, OTHER_EXPENSE, OTHER_INCOME
from app.categorization.domain.category import Category
from app.categorization.domain.rule import Rule


@dataclass(frozen=True)
class CategorizationPolicy:
    """Picks a category for a movement: the first matching rule, or a fallback category."""

    rules: Sequence[Rule]
    fallback_expense: int | None
    fallback_income: int | None
    bizum_income: int | None

    @classmethod
    def from_catalog(cls, categories: Sequence[Category], rules: Sequence[Rule]) -> "CategorizationPolicy":
        by_name = {c.name: c.id for c in categories}
        return cls(
            # Lower priority first; on ties, the rule created first
            rules=sorted(rules, key=lambda r: (r.priority, r.id or 0)),
            fallback_expense=by_name.get(OTHER_EXPENSE),
            fallback_income=by_name.get(OTHER_INCOME),
            bizum_income=by_name.get(BIZUM_INCOME),
        )

    def categorize(self, counterparty: str | None, description: str, is_income: bool) -> int | None:
        # Padded with spaces so patterns like "bar " can require a word boundary
        text = f" {counterparty or ''} {description} ".lower()
        for rule in self.rules:
            if rule.pattern.lower() in text:
                return rule.category_id
        if is_income:
            if "bizum" in text and self.bizum_income:
                return self.bizum_income
            return self.fallback_income
        return self.fallback_expense
