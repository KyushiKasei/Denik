"""Fáze 1: Place, typy, app_meta.

Revision ID: 001_phase1_places
Revises:
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_phase1_places"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "place_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_cs", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code", name="ux_place_types_code"),
    )
    op.create_table(
        "places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("short_name", sa.String(length=120)),
        sa.Column("alternative_names", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("short_description", sa.Text()),
        sa.Column("condition", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("visitability", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("address", sa.String(length=400)),
        sa.Column("municipality", sa.String(length=120)),
        sa.Column("municipality_code", sa.String(length=20)),
        sa.Column("district", sa.String(length=120)),
        sa.Column("district_code", sa.String(length=20)),
        sa.Column("region", sa.String(length=120)),
        sa.Column("region_code", sa.String(length=20)),
        sa.Column("country", sa.String(length=8), nullable=False, server_default="CZ"),
        sa.Column("official_website", sa.String(length=500)),
        sa.Column("wikipedia_url", sa.String(length=500)),
        sa.Column("opening_hours_url", sa.String(length=500)),
        sa.Column("ticket_url", sa.String(length=500)),
        sa.Column("heritage_status", sa.String(length=32)),
        sa.Column("unesco", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_status", sa.String(length=32), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.Column("archived_at", sa.String(length=40)),
        sa.UniqueConstraint("public_id", name="ux_places_public_id"),
    )
    op.create_index("ix_places_name", "places", ["name"])
    op.create_index("ix_places_municipality_district_region", "places", ["municipality", "district", "region"])
    op.create_index("ix_places_lat_lon", "places", ["latitude", "longitude"])
    op.create_index("ix_places_archived_at", "places", ["archived_at"])
    op.create_index("ix_places_quality_status", "places", ["quality_status"])
    op.create_table(
        "place_place_types",
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), primary_key=True),
        sa.Column("place_type_id", sa.Integer(), sa.ForeignKey("place_types.id"), primary_key=True),
    )
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
    op.drop_table("place_place_types")
    op.drop_index("ix_places_quality_status", table_name="places")
    op.drop_index("ix_places_archived_at", table_name="places")
    op.drop_index("ix_places_lat_lon", table_name="places")
    op.drop_index("ix_places_municipality_district_region", table_name="places")
    op.drop_index("ix_places_name", table_name="places")
    op.drop_table("places")
    op.drop_table("place_types")
