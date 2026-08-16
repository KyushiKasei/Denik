"""Fáze 3 doplněk: sloučení dvou existujících Place.

Revision ID: 003_merge_places
Revises: 002_phase3_import
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_merge_places"
down_revision: Union[str, Sequence[str], None] = "002_phase3_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("places") as batch:
        batch.add_column(sa.Column("merged_into_public_id", sa.String(length=36)))


def downgrade() -> None:
    with op.batch_alter_table("places") as batch:
        batch.drop_column("merged_into_public_id")
