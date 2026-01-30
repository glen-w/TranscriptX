"""
Migration: Add file tracking tables.

This migration adds tables for tracking file processing history with
single-entity identity (fingerprint-based) and artifact tracking for
multiple paths/locations per entity.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_file_tracking"
down_revision = "001_add_speaker_profiles"
branch_labels = None
depends_on = None


def upgrade():
    """Add file tracking tables."""

    # Create file_entities table
    op.create_table(
        "file_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_vector", sa.JSON(), nullable=False),
        sa.Column(
            "fingerprint_version", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("file_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint_hash"),
    )

    # Create indexes for file_entities
    op.create_index(
        "idx_file_entity_fingerprint",
        "file_entities",
        ["fingerprint_hash"],
        unique=True,
    )
    op.create_index("idx_file_entity_first_seen", "file_entities", ["first_seen_at"])
    op.create_index("idx_file_entity_last_seen", "file_entities", ["last_seen_at"])

    # Create file_artifacts table
    op.create_table(
        "file_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_entity_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("mtime", sa.DateTime(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_present", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("file_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["file_entity_id"], ["file_entities.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for file_artifacts
    op.create_index("idx_artifact_entity", "file_artifacts", ["file_entity_id"])
    op.create_index("idx_artifact_path", "file_artifacts", ["path"])
    op.create_index(
        "idx_artifact_role_current", "file_artifacts", ["role", "is_current"]
    )
    op.create_index("idx_artifact_present", "file_artifacts", ["is_present"])

    # Create file_processing_events table
    op.create_table(
        "file_processing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_uuid", sa.String(length=36), nullable=False),
        sa.Column("file_entity_id", sa.Integer(), nullable=False),
        sa.Column("source_artifact_id", sa.Integer(), nullable=True),
        sa.Column("target_artifact_id", sa.Integer(), nullable=True),
        sa.Column("pipeline_run_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_status", sa.String(length=50), nullable=False),
        sa.Column("source_path", sa.String(length=1000), nullable=True),
        sa.Column("target_path", sa.String(length=1000), nullable=True),
        sa.Column("operation_details", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("performed_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["file_entity_id"], ["file_entities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["file_artifacts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_artifact_id"], ["file_artifacts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid"),
    )

    # Create indexes for file_processing_events
    op.create_index(
        "idx_event_uuid", "file_processing_events", ["event_uuid"], unique=True
    )
    op.create_index("idx_event_entity", "file_processing_events", ["file_entity_id"])
    op.create_index("idx_event_pipeline", "file_processing_events", ["pipeline_run_id"])
    op.create_index(
        "idx_event_type_status",
        "file_processing_events",
        ["event_type", "event_status"],
    )
    op.create_index("idx_event_created", "file_processing_events", ["created_at"])

    # Create file_preprocessing_records table
    op.create_table(
        "file_preprocessing_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_entity_id", sa.Integer(), nullable=False),
        sa.Column("processing_event_id", sa.Integer(), nullable=False),
        sa.Column("source_artifact_id", sa.Integer(), nullable=True),
        sa.Column("target_artifact_id", sa.Integer(), nullable=True),
        sa.Column("preprocessing_summary", sa.JSON(), nullable=True),
        sa.Column("preprocessing_full_json", sa.JSON(), nullable=True),
        sa.Column("original_file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("processed_file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("applied_steps", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["file_entity_id"], ["file_entities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["processing_event_id"], ["file_processing_events.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["file_artifacts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_artifact_id"], ["file_artifacts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processing_event_id"),
    )

    # Create indexes for file_preprocessing_records
    op.create_index(
        "idx_preprocessing_entity", "file_preprocessing_records", ["file_entity_id"]
    )
    op.create_index(
        "idx_preprocessing_event",
        "file_preprocessing_records",
        ["processing_event_id"],
        unique=True,
    )

    # Create file_rename_history table
    op.create_table(
        "file_rename_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_entity_id", sa.Integer(), nullable=False),
        sa.Column("processing_event_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("rename_group_id", sa.String(length=36), nullable=False),
        sa.Column("old_path", sa.String(length=1000), nullable=False),
        sa.Column("new_path", sa.String(length=1000), nullable=False),
        sa.Column("old_name", sa.String(length=500), nullable=False),
        sa.Column("new_name", sa.String(length=500), nullable=False),
        sa.Column("rename_reason", sa.String(length=255), nullable=True),
        sa.Column("renamed_files", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["file_entity_id"], ["file_entities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["processing_event_id"], ["file_processing_events.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["file_artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for file_rename_history
    op.create_index("idx_rename_entity", "file_rename_history", ["file_entity_id"])
    op.create_index("idx_rename_event", "file_rename_history", ["processing_event_id"])
    op.create_index("idx_rename_group", "file_rename_history", ["rename_group_id"])
    op.create_index("idx_rename_artifact", "file_rename_history", ["artifact_id"])


def downgrade():
    """Remove file tracking tables."""

    # Drop file_rename_history table
    op.drop_index("idx_rename_artifact", table_name="file_rename_history")
    op.drop_index("idx_rename_group", table_name="file_rename_history")
    op.drop_index("idx_rename_event", table_name="file_rename_history")
    op.drop_index("idx_rename_entity", table_name="file_rename_history")
    op.drop_table("file_rename_history")

    # Drop file_preprocessing_records table
    op.drop_index("idx_preprocessing_event", table_name="file_preprocessing_records")
    op.drop_index("idx_preprocessing_entity", table_name="file_preprocessing_records")
    op.drop_table("file_preprocessing_records")

    # Drop file_processing_events table
    op.drop_index("idx_event_created", table_name="file_processing_events")
    op.drop_index("idx_event_type_status", table_name="file_processing_events")
    op.drop_index("idx_event_pipeline", table_name="file_processing_events")
    op.drop_index("idx_event_entity", table_name="file_processing_events")
    op.drop_index("idx_event_uuid", table_name="file_processing_events")
    op.drop_table("file_processing_events")

    # Drop file_artifacts table
    op.drop_index("idx_artifact_present", table_name="file_artifacts")
    op.drop_index("idx_artifact_role_current", table_name="file_artifacts")
    op.drop_index("idx_artifact_path", table_name="file_artifacts")
    op.drop_index("idx_artifact_entity", table_name="file_artifacts")
    op.drop_table("file_artifacts")

    # Drop file_entities table
    op.drop_index("idx_file_entity_last_seen", table_name="file_entities")
    op.drop_index("idx_file_entity_first_seen", table_name="file_entities")
    op.drop_index("idx_file_entity_fingerprint", table_name="file_entities")
    op.drop_table("file_entities")
