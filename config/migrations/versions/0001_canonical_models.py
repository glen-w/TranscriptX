"""Add canonical transcript models and run tracking.

Revision ID: 0001_canonical_models
Revises: None
Create Date: 2026-01-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

from transcriptx.database.models import Base

revision = "0001_canonical_models"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = inspect(op.get_bind()).get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = inspect(op.get_bind()).get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def _has_unique(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    uniques = inspect(op.get_bind()).get_unique_constraints(table_name)
    return any(constraint["name"] == constraint_name for constraint in uniques)


def upgrade() -> None:
    # Create all base tables if missing (bootstrap for fresh DBs)
    Base.metadata.create_all(bind=op.get_bind())

    # TranscriptFile additions
    if _has_table("transcript_files"):
        with op.batch_alter_table("transcript_files") as batch:
            if not _has_column("transcript_files", "source_uri"):
                batch.add_column(sa.Column("source_uri", sa.String(length=1000)))
            if not _has_column("transcript_files", "import_timestamp"):
                batch.add_column(sa.Column("import_timestamp", sa.DateTime()))
            if not _has_column("transcript_files", "transcript_content_hash"):
                batch.add_column(sa.Column("transcript_content_hash", sa.String(length=64)))
            if not _has_column("transcript_files", "schema_version"):
                batch.add_column(sa.Column("schema_version", sa.String(length=50)))
            if not _has_column("transcript_files", "sentence_schema_version"):
                batch.add_column(sa.Column("sentence_schema_version", sa.String(length=50)))
            if not _has_column("transcript_files", "source_hash"):
                batch.add_column(sa.Column("source_hash", sa.String(length=64)))

            if not _has_unique("transcript_files", "uq_transcript_content_schema"):
                batch.create_unique_constraint(
                    "uq_transcript_content_schema",
                    ["transcript_content_hash", "schema_version"],
                )

        if not _has_index("transcript_files", "idx_transcript_content_hash"):
            op.create_index(
                "idx_transcript_content_hash",
                "transcript_files",
                ["transcript_content_hash"],
            )

    # Transcript speakers
    if not _has_table("transcript_speakers"):
        op.create_table(
            "transcript_speakers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("transcript_file_id", sa.Integer(), sa.ForeignKey("transcript_files.id", ondelete="CASCADE"), nullable=False),
            sa.Column("speaker_label", sa.String(length=255), nullable=False),
            sa.Column("speaker_order", sa.Integer()),
            sa.Column("display_name", sa.String(length=255)),
            sa.Column("speaker_fingerprint", sa.String(length=255)),
            sa.Column("created_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("transcript_file_id", "speaker_label", name="uq_transcript_speaker_label"),
        )
        op.create_index("idx_transcript_speaker_file", "transcript_speakers", ["transcript_file_id"])

    # Transcript segments/sentences: transcript_speaker_id
    if _has_table("transcript_segments") and not _has_column("transcript_segments", "transcript_speaker_id"):
        with op.batch_alter_table("transcript_segments") as batch:
            batch.add_column(
                sa.Column("transcript_speaker_id", sa.Integer(), sa.ForeignKey("transcript_speakers.id", ondelete="SET NULL"))
            )
        if not _has_index("transcript_segments", "idx_segment_transcript_speaker"):
            op.create_index(
                "idx_segment_transcript_speaker",
                "transcript_segments",
                ["transcript_speaker_id"],
            )

    if _has_table("transcript_sentences") and not _has_column("transcript_sentences", "transcript_speaker_id"):
        with op.batch_alter_table("transcript_sentences") as batch:
            batch.add_column(
                sa.Column("transcript_speaker_id", sa.Integer(), sa.ForeignKey("transcript_speakers.id", ondelete="SET NULL"))
            )
        if not _has_index("transcript_sentences", "idx_sentence_transcript_speaker"):
            op.create_index(
                "idx_sentence_transcript_speaker",
                "transcript_sentences",
                ["transcript_speaker_id"],
            )

    # Pipeline runs
    if not _has_table("pipeline_runs"):
        op.create_table(
            "pipeline_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("transcript_file_id", sa.Integer(), sa.ForeignKey("transcript_files.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pipeline_version", sa.String(length=50)),
            sa.Column("pipeline_config_hash", sa.String(length=64)),
            sa.Column("pipeline_input_hash", sa.String(length=64)),
            sa.Column("cli_args_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=50), server_default="pending"),
            sa.Column("created_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_pipeline_run_file", "pipeline_runs", ["transcript_file_id"])
        op.create_index("idx_pipeline_run_status", "pipeline_runs", ["status"])

    # Module runs
    if not _has_table("module_runs"):
        op.create_table(
            "module_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("transcript_file_id", sa.Integer(), sa.ForeignKey("transcript_files.id", ondelete="CASCADE"), nullable=False),
            sa.Column("module_name", sa.String(length=100), nullable=False),
            sa.Column("module_version", sa.String(length=64)),
            sa.Column("module_config_hash", sa.String(length=64)),
            sa.Column("module_input_hash", sa.String(length=64)),
            sa.Column("output_hash", sa.String(length=64)),
            sa.Column("status", sa.String(length=50), server_default="pending"),
            sa.Column("duration_seconds", sa.Float()),
            sa.Column("is_cacheable", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("cache_reason", sa.String(length=255)),
            sa.Column("metrics_json", sa.JSON(), nullable=True),
            sa.Column("outputs_json", sa.JSON(), nullable=True),
            sa.Column("replaces_module_run_id", sa.Integer(), sa.ForeignKey("module_runs.id", ondelete="SET NULL")),
            sa.Column("superseded_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_module_run_pipeline", "module_runs", ["pipeline_run_id"])
        op.create_index("idx_module_run_module", "module_runs", ["module_name"])
        op.create_index("idx_module_run_input", "module_runs", ["module_name", "module_input_hash"])

    # Performance spans
    if not _has_table("performance_spans"):
        op.create_table(
            "performance_spans",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("trace_id", sa.String(length=32), nullable=False),
            sa.Column("span_id", sa.String(length=16), nullable=False),
            sa.Column("parent_span_id", sa.String(length=16)),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("kind", sa.String(length=20)),
            sa.Column("status_code", sa.String(length=10), server_default="OK"),
            sa.Column("status_message", sa.Text()),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime()),
            sa.Column("duration_ms", sa.Float()),
            sa.Column("attributes_json", sa.JSON(), nullable=True),
            sa.Column("events_json", sa.JSON(), nullable=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL")),
            sa.Column("module_run_id", sa.Integer(), sa.ForeignKey("module_runs.id", ondelete="SET NULL")),
            sa.Column("transcript_file_id", sa.Integer(), sa.ForeignKey("transcript_files.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("span_id", name="uq_performance_span_id"),
        )
        op.create_index("idx_span_trace_id", "performance_spans", ["trace_id"])
        op.create_index("idx_span_parent", "performance_spans", ["parent_span_id"])
        op.create_index("idx_span_start_time", "performance_spans", [sa.text("start_time DESC")])
        op.create_index("idx_span_name_start_time", "performance_spans", ["name", sa.text("start_time DESC")])
        op.create_index("idx_span_pipeline", "performance_spans", ["pipeline_run_id"])
        op.create_index("idx_span_module", "performance_spans", ["module_run_id"])
        op.create_index("idx_span_transcript", "performance_spans", ["transcript_file_id"])

        if op.get_bind().dialect.name == "postgresql":
            op.create_index(
                "idx_span_attributes_gin",
                "performance_spans",
                ["attributes_json"],
                postgresql_using="gin",
            )

    # Artifact index
    if not _has_table("artifact_index"):
        op.create_table(
            "artifact_index",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("module_run_id", sa.Integer(), sa.ForeignKey("module_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("transcript_file_id", sa.Integer(), sa.ForeignKey("transcript_files.id", ondelete="CASCADE"), nullable=False),
            sa.Column("artifact_key", sa.String(length=500), nullable=False),
            sa.Column("artifact_type", sa.String(length=50)),
            sa.Column("artifact_role", sa.String(length=50), server_default="primary"),
            sa.Column("relative_path", sa.String(length=1000), nullable=False),
            sa.Column("artifact_root", sa.String(length=1000)),
            sa.Column("content_hash", sa.String(length=64)),
            sa.Column("created_at", sa.DateTime(), server_default=text("CURRENT_TIMESTAMP")),
            sa.Column("exists_last_checked_at", sa.DateTime()),
            sa.UniqueConstraint("module_run_id", "artifact_key", name="uq_module_run_artifact_key"),
        )
        op.create_index("idx_artifact_transcript", "artifact_index", ["transcript_file_id"])
        op.create_index("idx_artifact_content", "artifact_index", ["content_hash"])
        op.create_index("idx_artifact_type", "artifact_index", ["artifact_type"])


def downgrade() -> None:
    if _has_table("performance_spans"):
        if _has_index("performance_spans", "idx_span_attributes_gin"):
            op.drop_index("idx_span_attributes_gin", table_name="performance_spans")
        op.drop_index("idx_span_transcript", table_name="performance_spans")
        op.drop_index("idx_span_module", table_name="performance_spans")
        op.drop_index("idx_span_pipeline", table_name="performance_spans")
        op.drop_index("idx_span_name_start_time", table_name="performance_spans")
        op.drop_index("idx_span_start_time", table_name="performance_spans")
        op.drop_index("idx_span_parent", table_name="performance_spans")
        op.drop_index("idx_span_trace_id", table_name="performance_spans")
        op.drop_table("performance_spans")

    if _has_table("artifact_index"):
        op.drop_index("idx_artifact_type", table_name="artifact_index")
        op.drop_index("idx_artifact_content", table_name="artifact_index")
        op.drop_index("idx_artifact_transcript", table_name="artifact_index")
        op.drop_table("artifact_index")

    if _has_table("module_runs"):
        op.drop_index("idx_module_run_input", table_name="module_runs")
        op.drop_index("idx_module_run_module", table_name="module_runs")
        op.drop_index("idx_module_run_pipeline", table_name="module_runs")
        op.drop_table("module_runs")

    if _has_table("pipeline_runs"):
        op.drop_index("idx_pipeline_run_status", table_name="pipeline_runs")
        op.drop_index("idx_pipeline_run_file", table_name="pipeline_runs")
        op.drop_table("pipeline_runs")

    if _has_table("transcript_segments") and _has_column("transcript_segments", "transcript_speaker_id"):
        with op.batch_alter_table("transcript_segments") as batch:
            batch.drop_column("transcript_speaker_id")

    if _has_table("transcript_sentences") and _has_column("transcript_sentences", "transcript_speaker_id"):
        with op.batch_alter_table("transcript_sentences") as batch:
            batch.drop_column("transcript_speaker_id")

    if _has_table("transcript_speakers"):
        op.drop_index("idx_transcript_speaker_file", table_name="transcript_speakers")
        op.drop_table("transcript_speakers")

    if _has_table("transcript_files"):
        if _has_index("transcript_files", "idx_transcript_content_hash"):
            op.drop_index("idx_transcript_content_hash", table_name="transcript_files")
        with op.batch_alter_table("transcript_files") as batch:
            if _has_unique("transcript_files", "uq_transcript_content_schema"):
                batch.drop_constraint("uq_transcript_content_schema", type_="unique")
            for col in [
                "source_uri",
                "import_timestamp",
                "transcript_content_hash",
                "schema_version",
                "sentence_schema_version",
                "source_hash",
            ]:
                if _has_column("transcript_files", col):
                    batch.drop_column(col)
