"""OSM opening_hours řetězec u Place.

Revision ID: 006_osm_hours
Revises: 005_trips
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_osm_hours"
down_revision: Union[str, Sequence[str], None] = "005_trips"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("places", sa.Column("osm_opening_hours", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "osm_opening_hours")
