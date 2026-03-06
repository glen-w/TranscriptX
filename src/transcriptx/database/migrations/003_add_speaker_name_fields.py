"""
Migration: Add first_name, surname, and personal_note fields to speakers table.

This migration adds fields to support better speaker identification and
disambiguation when multiple speakers share the same name.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_speaker_name_fields"
down_revision = "002_add_file_tracking"
branch_labels = None
depends_on = None


def upgrade():
    """Add first_name, surname, and personal_note fields to speakers table."""

    # Add new columns to speakers table
    op.add_column(
        "speakers", sa.Column("first_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "speakers", sa.Column("surname", sa.String(length=255), nullable=True)
    )
    op.add_column("speakers", sa.Column("personal_note", sa.Text(), nullable=True))

    # Create indexes for the new fields
    op.create_index("idx_speaker_first_name", "speakers", ["first_name"])
    op.create_index("idx_speaker_surname", "speakers", ["surname"])
    op.create_index("idx_speaker_name_composite", "speakers", ["first_name", "surname"])

    # Try to parse existing names into first_name and surname
    # This is a best-effort migration - we'll parse names that look like "First Last"
    connection = op.get_bind()

    # Update existing speakers: try to parse name into first_name/surname
    # Only update if first_name is NULL (not already set)
    connection.execute(
        sa.text(
            """
        UPDATE speakers 
        SET first_name = CASE 
            WHEN name LIKE '% %' THEN 
                SUBSTR(name, 1, INSTR(name, ' ') - 1)
            ELSE 
                name
        END,
        surname = CASE 
            WHEN name LIKE '% %' THEN 
                SUBSTR(name, INSTR(name, ' ') + 1)
            ELSE 
                NULL
        END
        WHERE first_name IS NULL
    """
        )
    )


def downgrade():
    """Remove first_name, surname, and personal_note fields from speakers table."""

    # Drop indexes
    op.drop_index("idx_speaker_name_composite", table_name="speakers")
    op.drop_index("idx_speaker_surname", table_name="speakers")
    op.drop_index("idx_speaker_first_name", table_name="speakers")

    # Drop columns
    op.drop_column("speakers", "personal_note")
    op.drop_column("speakers", "surname")
    op.drop_column("speakers", "first_name")
