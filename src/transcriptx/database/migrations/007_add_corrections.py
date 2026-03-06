"""
Migration: Add correction_sessions, correction_candidates, correction_decisions,
and correction_rules_db tables.
"""

from alembic import op
import sqlalchemy as sa


revision = "007_add_corrections"
down_revision = "006_add_groups"
branch_labels = None
depends_on = None


def upgrade():
    # correction_sessions first (referenced by correction_rules_db and correction_candidates)
    op.create_table(
        "correction_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "transcript_file_id",
            sa.Integer(),
            sa.ForeignKey("transcript_files.id"),
            nullable=True,
        ),
        sa.Column("transcript_path", sa.String(length=1000), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("detector_version", sa.String(length=40), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="active"
        ),
        sa.Column("ui_state_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_correction_session_path_status",
        "correction_sessions",
        ["transcript_path", "status"],
    )

    # correction_rules_db (references correction_sessions)
    op.create_table(
        "correction_rules_db",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("rule_hash", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("rule_type", sa.String(length=20), nullable=False),
        sa.Column("wrong_variants_json", sa.JSON(), nullable=False),
        sa.Column("replacement_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.0"),
        sa.Column("auto_apply", sa.Boolean(), server_default="0"),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("is_person_name", sa.Boolean(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="1"),
        sa.Column(
            "source_session_id",
            sa.String(length=36),
            sa.ForeignKey("correction_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("transcript_path", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_correction_rule_hash_scope_path",
        "correction_rules_db",
        ["rule_hash", "scope", "transcript_path"],
    )

    op.create_table(
        "correction_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("correction_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_hash", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("wrong_text", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rule_id", sa.String(length=40), nullable=True),
        sa.Column("occurrences_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_correction_candidate_session_status",
        "correction_candidates",
        ["session_id", "status"],
    )

    op.create_table(
        "correction_decisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("correction_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(length=36),
            sa.ForeignKey("correction_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("selected_occurrence_ids_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_rule_id",
            sa.String(length=36),
            sa.ForeignKey("correction_rules_db.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=50), nullable=False, server_default="web"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_correction_decision_session_candidate",
        "correction_decisions",
        ["session_id", "candidate_id"],
    )
    op.create_index(
        "idx_correction_decision_candidate_id",
        "correction_decisions",
        ["candidate_id"],
    )


def downgrade():
    op.drop_index(
        "idx_correction_decision_candidate_id",
        table_name="correction_decisions",
    )
    op.drop_constraint(
        "uq_correction_decision_session_candidate",
        "correction_decisions",
        type_="unique",
    )
    op.drop_table("correction_decisions")

    op.drop_index(
        "idx_correction_candidate_session_status",
        table_name="correction_candidates",
    )
    op.drop_table("correction_candidates")

    op.drop_index(
        "idx_correction_session_path_status",
        table_name="correction_sessions",
    )
    op.drop_table("correction_sessions")

    op.drop_constraint(
        "uq_correction_rule_hash_scope_path",
        "correction_rules_db",
        type_="unique",
    )
    op.drop_table("correction_rules_db")
