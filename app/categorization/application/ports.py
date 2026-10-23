"""What the categorization use cases need from the outside world; infrastructure provides the implementations."""

from collections.abc import Collection
from types import TracebackType
from typing import Protocol, Self

from app.categorization.domain.category import Category
from app.categorization.domain.rule import Rule
from app.shared.ids import CategoryId


class CategoryRepository(Protocol):
    def any(self) -> bool: ...

    def list_for_display(self) -> list[Category]:
        """Income categories first, then expense categories, each sorted by name (database collation)."""
        ...

    def all(self) -> list[Category]: ...

    def by_ids(self, ids: Collection[CategoryId]) -> list[Category]: ...

    def exists(self, category_id: CategoryId) -> bool: ...

    def add(self, category: Category) -> None:
        """Stores the category and sets its `id`."""
        ...


class RuleRepository(Protocol):
    def all(self) -> list[Rule]: ...

    def add(self, rule: Rule) -> None: ...


class UnitOfWork(Protocol):
    """One transaction: changes are kept only if `commit()` is called before leaving the block."""

    @property
    def categories(self) -> CategoryRepository: ...

    @property
    def rules(self) -> RuleRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None: ...

    def commit(self) -> None: ...
