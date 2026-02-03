"""
Migration: Add groups and group_members tables.
"""

from alembic import op
import sqlalchemy as sa


revision = "006_add_groups"
down_revision = "005_add_transcript_sets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), unique=True, nullable=False),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False, server_default="merged_event"),
        sa.Column("key", sa.String(length=72), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("uq_groups_key", "groups", ["key"], unique=True)
    op.create_index("uq_groups_name", "groups", ["name"], unique=True)
    op.create_index("idx_groups_type", "groups", ["type"])

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transcript_file_id",
            sa.Integer(),
            sa.ForeignKey("transcript_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_group_member_position",
        "group_members",
        ["group_id", "position"],
    )
    op.create_unique_constraint(
        "uq_group_member_position",
        "group_members",
        ["group_id", "position"],
    )
    op.create_unique_constraint(
        "uq_group_member_transcript",
        "group_members",
        ["group_id", "transcript_file_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_group_member_transcript", "group_members", type_="unique"
    )
    op.drop_constraint(
        "uq_group_member_position", "group_members", type_="unique"
    )
    op.drop_index("idx_group_member_position", table_name="group_members")
    op.drop_table("group_members")

    op.drop_index("idx_groups_type", table_name="groups")
    op.drop_index("uq_groups_name", table_name="groups")
    op.drop_index("uq_groups_key", table_name="groups")
    op.drop_table("groups")
