from collections.abc import Callable, Collection
from types import TracebackType
from typing import Self, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorization.domain.category import Category, CategoryKind
from app.categorization.domain.rule import Rule
from app.categorization.infrastructure.orm import CategoryRow, RuleRow


def _category(row: CategoryRow) -> Category:
    return Category(id=row.id, name=row.name, kind=cast(CategoryKind, row.kind), icon=row.icon, color=row.color)


class SqlCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def any(self) -> bool:
        return self.db.scalar(select(CategoryRow.id).limit(1)) is not None

    def list_for_display(self) -> list[Category]:
        # "income" > "expense", so descending kind puts income first
        rows = self.db.scalars(select(CategoryRow).order_by(CategoryRow.kind.desc(), CategoryRow.name))
        return [_category(row) for row in rows]

    def all(self) -> list[Category]:
        return [_category(row) for row in self.db.scalars(select(CategoryRow))]

    def by_ids(self, ids: Collection[int]) -> list[Category]:
        return [_category(row) for row in self.db.scalars(select(CategoryRow).where(CategoryRow.id.in_(ids)))]

    def exists(self, category_id: int) -> bool:
        return self.db.get(CategoryRow, category_id) is not None

    def add(self, category: Category) -> None:
        row = CategoryRow(name=category.name, kind=category.kind, icon=category.icon, color=category.color)
        self.db.add(row)
        self.db.flush()
        category.id = row.id


class SqlRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def all(self) -> list[Rule]:
        rows = self.db.scalars(select(RuleRow).order_by(RuleRow.priority, RuleRow.id))
        return [Rule(id=r.id, pattern=r.pattern, category_id=r.category_id, priority=r.priority) for r in rows]

    def add(self, rule: Rule) -> None:
        row = RuleRow(pattern=rule.pattern, category_id=rule.category_id, priority=rule.priority)
        self.db.add(row)
        self.db.flush()
        rule.id = row.id


class SqlUnitOfWork:
    """A SQLAlchemy session per `with` block; anything not committed is rolled back when the block ends."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> Self:
        self.db = self.session_factory()
        self._categories = SqlCategoryRepository(self.db)
        self._rules = SqlRuleRepository(self.db)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.db.rollback()
        self.db.close()

    @property
    def categories(self) -> SqlCategoryRepository:
        return self._categories

    @property
    def rules(self) -> SqlRuleRepository:
        return self._rules

    def commit(self) -> None:
        self.db.commit()
