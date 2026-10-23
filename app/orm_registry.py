"""Imports every context's ORM rows so `Base.metadata` holds every table (migrations, schema checks).

Composition-level module: like app.bootstrap, it may reach into context internals.
"""

from app.banking.infrastructure import orm as banking_orm
from app.categorization.infrastructure import orm as categorization_orm
from app.db import Base
from app.identity.infrastructure import orm as identity_orm
from app.transactions.infrastructure import orm as transactions_orm

ORM_MODULES = (banking_orm, categorization_orm, identity_orm, transactions_orm)
metadata = Base.metadata
