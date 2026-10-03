"""Add locality to stops.

Revision ID: 20261003_02
Revises: 20261003_01
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_02"
down_revision: str | Sequence[str] | None = "20261003_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stops",
        sa.Column("locality", sa.String(length=120), server_default="unknown", nullable=False),
    )
    op.create_index("ix_stops_locality_kind", "stops", ["locality", "kind"])


def downgrade() -> None:
    op.drop_index("ix_stops_locality_kind", table_name="stops")
    op.drop_column("stops", "locality")
