"""Typed references between contexts; plain ints at runtime."""

from typing import NewType

AccountId = NewType("AccountId", int)
CategoryId = NewType("CategoryId", int)
TransactionId = NewType("TransactionId", int)


class UnsavedEntity(Exception):
    """An entity was used as persisted before its repository gave it an id."""


def saved_id[T](entity_id: T | None, entity: str) -> T:
    """The id of an entity that must already be persisted; fails loudly (unlike `assert`, also under `python -O`)."""
    if entity_id is None:
        raise UnsavedEntity(f"{entity} has no id: it must be saved first")
    return entity_id
