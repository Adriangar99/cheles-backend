"""transactions.source: bank or an imported file

Revision ID: 0003_transaction_source
Revises: 0002_kind_manual
Create Date: 2026-10-25 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_transaction_source"
down_revision: str | None = "0002_kind_manual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("source", sa.String(8), server_default="bank", nullable=False))


def downgrade() -> None:
    op.drop_column("transactions", "source")
