"""transactions.kind_manual: the ⇄ mark set by hand

Revision ID: 0002_kind_manual
Revises: 0001_baseline
Create Date: 2026-10-24 23:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_kind_manual"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("kind_manual", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("transactions", "kind_manual")
