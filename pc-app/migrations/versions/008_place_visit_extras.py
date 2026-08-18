"""Pes, platba, zázemí, sloh a rok vzniku.

Revision ID: 008_place_visit_extras
Revises: 007_travel_ops
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_place_visit_extras"
down_revision: Union[str, Sequence[str], None] = "007_travel_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("places", sa.Column("dogs", sa.String(length=40), nullable=True))
    op.add_column("places", sa.Column("payment", sa.String(length=40), nullable=True))
    op.add_column("places", sa.Column("amenities", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("places", sa.Column("inception_year", sa.Integer(), nullable=True))
    op.add_column("places", sa.Column("architectural_style", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "architectural_style")
    op.drop_column("places", "inception_year")
    op.drop_column("places", "amenities")
    op.drop_column("places", "payment")
    op.drop_column("places", "dogs")
