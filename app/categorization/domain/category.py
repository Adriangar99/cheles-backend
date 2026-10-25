from dataclasses import dataclass
from typing import Literal, get_args

from app.shared.ids import CategoryId

CategoryKind = Literal["expense", "income"]
CATEGORY_KINDS: tuple[CategoryKind, ...] = get_args(CategoryKind)


@dataclass
class Category:
    """`id` is None until the category is stored."""

    name: str
    kind: CategoryKind
    icon: str
    color: str
    id: CategoryId | None = None


@dataclass(frozen=True)
class CategoryLabel:
    """How other contexts show a category."""

    id: CategoryId
    name: str
    icon: str
    color: str
