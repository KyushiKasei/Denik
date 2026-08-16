"""Fáze výlety: trips a trip_stops v osobním deníku.

Revision ID: 005_trips
Revises: 004_phase8_diary
Create Date: 2026-08-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_trips"
down_revision: Union[str, Sequence[str], None] = "004_phase8_diary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("planned_on", sa.String(length=10)),
        sa.Column("origin_latitude", sa.Float()),
        sa.Column("origin_longitude", sa.Float()),
        sa.Column("origin_label", sa.String(length=200)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.Column("deleted_at", sa.String(length=40)),
        sa.UniqueConstraint("public_id", name="ux_trips_public_id"),
    )
    op.create_index("ix_trips_deleted_at", "trips", ["deleted_at"])

    op.create_table(
        "trip_stops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=True),
        sa.Column("place_public_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text()),
    )
    op.create_index("ix_trip_stops_trip_id", "trip_stops", ["trip_id"])
    op.create_index("ix_trip_stops_place_id", "trip_stops", ["place_id"])
    op.create_index("ix_trip_stops_place_public_id", "trip_stops", ["place_public_id"])


def downgrade() -> None:
    op.drop_table("trip_stops")
    op.drop_table("trips")
