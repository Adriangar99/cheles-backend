"""Unit tests for the rule engine every sync and reprocess relies on (pure domain)."""

from app.categorization.domain.category import Category
from app.categorization.domain.policy import CategorizationPolicy
from app.categorization.domain.rule import Rule
from app.shared.ids import CategoryId

CATEGORIES = [
    Category(id=CategoryId(1), name="Supermercado", kind="expense", icon="🛒", color="#000"),
    Category(id=CategoryId(2), name="Restaurantes", kind="expense", icon="🍽", color="#000"),
    Category(id=CategoryId(3), name="Ocio", kind="expense", icon="🎟", color="#000"),
    Category(id=CategoryId(4), name="Otros gastos", kind="expense", icon="•", color="#000"),
    Category(id=CategoryId(5), name="Bizum recibido", kind="income", icon="📲", color="#000"),
    Category(id=CategoryId(6), name="Otros ingresos", kind="income", icon="•", color="#000"),
]


def policy(*rules: Rule) -> CategorizationPolicy:
    return CategorizationPolicy.from_catalog(CATEGORIES, list(rules))


def test_first_matching_rule_by_priority_then_creation_order() -> None:
    engine = policy(
        Rule(id=1, pattern="mercadona", category_id=CategoryId(1), priority=100),
        Rule(id=3, pattern="mercadona", category_id=CategoryId(3), priority=10),
        Rule(id=2, pattern="mercadona", category_id=CategoryId(2), priority=10),
    )

    assert engine.categorize("MERCADONA", "", is_income=False) == 2


def test_matches_case_insensitively_on_counterparty_and_description() -> None:
    engine = policy(Rule(id=1, pattern="Mercadona", category_id=CategoryId(1), priority=100))

    assert engine.categorize(None, "compra MERCADONA valencia", is_income=False) == 1
    assert engine.categorize("mercadona sa", "", is_income=False) == 1


def test_patterns_with_a_trailing_space_need_a_word_boundary() -> None:
    engine = policy(Rule(id=1, pattern="bar ", category_id=CategoryId(2), priority=100))

    assert engine.categorize("BARCELONA PARKING", "", is_income=False) == 4
    assert engine.categorize("BAR PEPE", "", is_income=False) == 2
    assert engine.categorize(None, "cena en el bar", is_income=False) == 2  # the text ends with a space


def test_fallbacks() -> None:
    engine = policy()

    assert engine.categorize(None, "BIZUM DE JUAN", is_income=True) == 5
    assert engine.categorize(None, "DEVOLUCION", is_income=True) == 6
    assert engine.categorize(None, "CARGO", is_income=False) == 4


def test_rules_apply_regardless_of_the_category_kind() -> None:
    engine = policy(Rule(id=1, pattern="mercadona", category_id=CategoryId(1), priority=100))

    assert engine.categorize("MERCADONA", "", is_income=True) == 1
