"""Praktická pole z OSM a stav výletu.

Revision ID: 007_travel_ops
Revises: 006_osm_hours
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_travel_ops"
down_revision: Union[str, Sequence[str], None] = "006_osm_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("places", sa.Column("phone", sa.String(length=80), nullable=True))
    op.add_column("places", sa.Column("fee", sa.String(length=40), nullable=True))
    op.add_column("places", sa.Column("wheelchair", sa.String(length=40), nullable=True))
    op.add_column("places", sa.Column("parking", sa.String(length=80), nullable=True))
    op.add_column("places", sa.Column("visit_duration_minutes", sa.Integer(), nullable=True))
    op.add_column("places", sa.Column("last_entry", sa.String(length=40), nullable=True))
    op.add_column("visits", sa.Column("trip_public_id", sa.String(length=36), nullable=True))
    op.add_column("trips", sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"))


def downgrade() -> None:
    op.drop_column("trips", "status")
    op.drop_column("visits", "trip_public_id")
    op.drop_column("places", "last_entry")
    op.drop_column("places", "visit_duration_minutes")
    op.drop_column("places", "parking")
    op.drop_column("places", "wheelchair")
    op.drop_column("places", "fee")
    op.drop_column("places", "phone")
