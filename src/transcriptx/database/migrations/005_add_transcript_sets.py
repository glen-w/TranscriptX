"""
Migration: Add transcript set tables.
"""

from alembic import op
import sqlalchemy as sa


revision = "005_add_transcript_sets"
down_revision = "004_add_sentence_vocabulary_resolution"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transcript_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), unique=True, nullable=False),
        sa.Column("name", sa.String(length=500), nullable=True, index=True),
        sa.Column("transcript_ids", sa.JSON(), nullable=True),
        sa.Column("set_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_transcript_set_created_at", "transcript_sets", ["created_at"])

    op.create_table(
        "transcript_set_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "set_id",
            sa.Integer(),
            sa.ForeignKey("transcript_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transcript_file_id",
            sa.Integer(),
            sa.ForeignKey("transcript_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_transcript_set_member_order",
        "transcript_set_members",
        ["set_id", "order_index"],
    )
    op.create_unique_constraint(
        "uq_transcript_set_member",
        "transcript_set_members",
        ["set_id", "transcript_file_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_transcript_set_member", "transcript_set_members", type_="unique"
    )
    op.drop_index(
        "idx_transcript_set_member_order", table_name="transcript_set_members"
    )
    op.drop_table("transcript_set_members")
    op.drop_index("idx_transcript_set_created_at", table_name="transcript_sets")
    op.drop_table("transcript_sets")
