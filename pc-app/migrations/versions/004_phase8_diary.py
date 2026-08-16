"""Fáze 8: osobní deník — visits, place_journal_states, diary_import_issues.

Revision ID: 004_phase8_diary
Revises: 003_merge_places
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_phase8_diary"
down_revision: Union[str, Sequence[str], None] = "003_merge_places"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=True),
        sa.Column("place_public_id", sa.String(length=36), nullable=False),
        sa.Column("visited_at", sa.String(length=10)),
        sa.Column("rating", sa.Integer()),
        sa.Column("people_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.Column("deleted_at", sa.String(length=40)),
        sa.UniqueConstraint("public_id", name="ux_visits_public_id"),
    )
    op.create_index("ix_visits_place_id", "visits", ["place_id"])
    op.create_index("ix_visits_place_public_id", "visits", ["place_public_id"])
    op.create_index("ix_visits_deleted_at", "visits", ["deleted_at"])

    op.create_table(
        "place_journal_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place_public_id", sa.String(length=36), nullable=False),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=True),
        sa.Column("want_to_visit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorite", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("personal_note", sa.Text()),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.Column("deleted_at", sa.String(length=40)),
        sa.UniqueConstraint("place_public_id", name="ux_place_journal_states_place_public_id"),
    )
    op.create_index("ix_place_journal_states_place_id", "place_journal_states", ["place_id"])

    op.create_table(
        "diary_import_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place_public_id", sa.String(length=36), nullable=False),
        sa.Column("visit_public_id", sa.String(length=36)),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("resolved_at", sa.String(length=40)),
    )
    op.create_index("ix_diary_import_issues_place_public_id", "diary_import_issues", ["place_public_id"])
    op.create_index("ix_diary_import_issues_resolved_at", "diary_import_issues", ["resolved_at"])


def downgrade() -> None:
    op.drop_table("diary_import_issues")
    op.drop_table("place_journal_states")
    op.drop_table("visits")
