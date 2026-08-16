"""Fáze 3: zdroje, override, importní běhy a review.

Revision ID: 002_phase3_import
Revises: 001_phase1_places
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_phase3_import"
down_revision: Union[str, Sequence[str], None] = "001_phase1_places"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "place_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=200)),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("fetched_at", sa.String(length=40)),
        sa.Column("license", sa.String(length=80)),
        sa.Column("raw_data", sa.Text()),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_place_sources_place_id", "place_sources", ["place_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX ux_place_sources_external
          ON place_sources(source_type, external_id)
          WHERE external_id IS NOT NULL AND external_id != ''
        """
    )

    op.create_table(
        "place_source_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "place_source_id",
            sa.Integer(),
            sa.ForeignKey("place_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("place_source_id", "field_name", name="ux_place_source_values_field"),
    )

    op.create_table(
        "place_field_overrides",
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), primary_key=True),
        sa.Column("field_name", sa.String(length=80), primary_key=True),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "place_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("original_url", sa.String(length=500)),
        sa.Column("thumbnail_url", sa.String(length=500)),
        sa.Column("author", sa.String(length=300)),
        sa.Column("license", sa.String(length=80)),
        sa.Column("license_url", sa.String(length=500)),
        sa.Column("attribution", sa.Text()),
        sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_place_photos_place_id", "place_photos", ["place_id"])

    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.String(length=40), nullable=False),
        sa.Column("finished_at", sa.String(length=40)),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_ignored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("backup_path", sa.Text()),
        sa.Column("log", sa.Text()),
    )

    op.create_table(
        "import_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "import_run_id",
            sa.Integer(),
            sa.ForeignKey("import_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=200)),
        sa.Column("candidate_place_id", sa.Integer(), sa.ForeignKey("places.id")),
        sa.Column("match_score", sa.Float()),
        sa.Column("match_reason", sa.Text()),
        sa.Column("raw_data", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text()),
        sa.Column("resolved_at", sa.String(length=40)),
    )
    op.create_index("ix_import_reviews_run_id", "import_reviews", ["import_run_id"])
    op.create_index("ix_import_reviews_status", "import_reviews", ["status"])
    op.create_index("ix_import_reviews_external_id", "import_reviews", ["external_id"])

    op.create_table(
        "import_review_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "import_review_id",
            sa.Integer(),
            sa.ForeignKey("import_reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("reason", sa.Text()),
    )
    op.create_index("ix_import_review_candidates_review_id", "import_review_candidates", ["import_review_id"])

    op.create_table(
        "import_field_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "import_run_id",
            sa.Integer(),
            sa.ForeignKey("import_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("place_id", sa.Integer(), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("old_source_value", sa.Text()),
        sa.Column("new_source_value", sa.Text()),
        sa.Column("master_value", sa.Text()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.String(length=40)),
    )
    op.create_index("ix_import_field_changes_run_id", "import_field_changes", ["import_run_id"])
    op.create_index("ix_import_field_changes_place_id", "import_field_changes", ["place_id"])


def downgrade() -> None:
    op.drop_index("ix_import_field_changes_place_id", table_name="import_field_changes")
    op.drop_index("ix_import_field_changes_run_id", table_name="import_field_changes")
    op.drop_table("import_field_changes")
    op.drop_index("ix_import_review_candidates_review_id", table_name="import_review_candidates")
    op.drop_table("import_review_candidates")
    op.drop_index("ix_import_reviews_external_id", table_name="import_reviews")
    op.drop_index("ix_import_reviews_status", table_name="import_reviews")
    op.drop_index("ix_import_reviews_run_id", table_name="import_reviews")
    op.drop_table("import_reviews")
    op.drop_table("import_runs")
    op.drop_index("ix_place_photos_place_id", table_name="place_photos")
    op.drop_table("place_photos")
    op.drop_table("place_field_overrides")
    op.drop_table("place_source_values")
    op.execute("DROP INDEX IF EXISTS ux_place_sources_external")
    op.drop_index("ix_place_sources_place_id", table_name="place_sources")
    op.drop_table("place_sources")
