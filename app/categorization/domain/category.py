from dataclasses import dataclass
from typing import Literal

from app.shared.ids import CategoryId

CategoryKind = Literal["expense", "income"]


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
