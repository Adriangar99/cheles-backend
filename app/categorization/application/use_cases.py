from collections.abc import Collection
from dataclasses import dataclass

from app.categorization.application.ports import UnitOfWork
from app.categorization.domain.catalog import DEFAULT_CATALOG
from app.categorization.domain.category import Category, CategoryLabel
from app.categorization.domain.errors import UnknownCategory
from app.categorization.domain.policy import CategorizationPolicy
from app.categorization.domain.rule import DEFAULT_RULE_PRIORITY, USER_RULE_PRIORITY, Rule


@dataclass
class SeedDefaultCatalog:
    """Creates the default categories and rules, only when there are no categories at all."""

    uow: UnitOfWork

    def __call__(self) -> None:
        with self.uow:
            if self.uow.categories.any():
                return
            for name, kind, icon, color, patterns in DEFAULT_CATALOG:
                category = Category(name=name, kind=kind, icon=icon, color=color)
                self.uow.categories.add(category)
                assert category.id is not None
                for pattern in patterns:
                    self.uow.rules.add(Rule(pattern=pattern, category_id=category.id, priority=DEFAULT_RULE_PRIORITY))
            self.uow.commit()


@dataclass
class ListCategories:
    uow: UnitOfWork

    def __call__(self) -> list[Category]:
        with self.uow:
            return self.uow.categories.list_for_display()


@dataclass
class CreateRule:
    uow: UnitOfWork

    def __call__(self, pattern: str, category_id: int) -> Rule:
        with self.uow:
            if not self.uow.categories.exists(category_id):
                raise UnknownCategory()
            rule = Rule(pattern=pattern.strip(), category_id=category_id, priority=USER_RULE_PRIORITY)
            self.uow.rules.add(rule)
            self.uow.commit()
        return rule


@dataclass
class CategoryExists:
    uow: UnitOfWork

    def __call__(self, category_id: int) -> bool:
        with self.uow:
            return self.uow.categories.exists(category_id)


@dataclass
class LoadPolicy:
    """Reads the current categories and rules into a policy to categorize many movements at once."""

    uow: UnitOfWork

    def __call__(self) -> CategorizationPolicy:
        with self.uow:
            return CategorizationPolicy.from_catalog(self.uow.categories.all(), self.uow.rules.all())


@dataclass
class CategoryLabels:
    uow: UnitOfWork

    def __call__(self, ids: Collection[int]) -> dict[int, CategoryLabel]:
        with self.uow:
            return {
                c.id: CategoryLabel(id=c.id, name=c.name, icon=c.icon, color=c.color)
                for c in self.uow.categories.by_ids(ids)
                if c.id is not None
            }


@dataclass(frozen=True)
class CategorizationServices:
    """The categorization use cases bound to one unit of work."""

    seed_default_catalog: SeedDefaultCatalog
    list_categories: ListCategories
    create_rule: CreateRule
    category_exists: CategoryExists
    load_policy: LoadPolicy
    category_labels: CategoryLabels
