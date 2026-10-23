"""Typed references between contexts; plain ints at runtime."""

from typing import NewType

AccountId = NewType("AccountId", int)
CategoryId = NewType("CategoryId", int)
TransactionId = NewType("TransactionId", int)
