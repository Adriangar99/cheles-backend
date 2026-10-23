from dataclasses import dataclass
from typing import Literal

CategoryKind = Literal["expense", "income"]


@dataclass
class Category:
    """`id` is None until the category is stored."""

    name: str
    kind: CategoryKind
    icon: str
    color: str
    id: int | None = None


@dataclass(frozen=True)
class CategoryLabel:
    """How other contexts show a category."""

    id: int
    name: str
    icon: str
    color: str
