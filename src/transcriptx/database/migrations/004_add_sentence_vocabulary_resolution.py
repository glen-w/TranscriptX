"""
Migration: Add sentence storage, vocabulary storage, and resolution event tables.

This migration adds:
- transcript_sentences: Sentence-level transcript storage with speaker_id and timestamps
- speaker_vocabulary_words: TF-IDF vocabulary words with speaker_id for speaker identification
- speaker_resolution_events: Schema-backed log of speaker identity resolution events
- Updates transcript_segments to include sentences relationship
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_add_sentence_vocabulary_resolution"
down_revision = "003_add_speaker_name_fields"
branch_labels = None
depends_on = None


def upgrade():
    """Add sentence storage, vocabulary storage, and resolution event tables."""

    # Create transcript_sentences table
    op.create_table(
        "transcript_sentences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("transcript_segment_id", sa.Integer(), nullable=False),
        sa.Column("speaker_id", sa.Integer(), nullable=True),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column(
            "timestamp_estimated", sa.Boolean(), nullable=True, server_default="1"
        ),
        sa.Column(
            "split_method",
            sa.String(length=50),
            nullable=True,
            server_default="punctuation",
        ),
        sa.Column(
            "provenance_version", sa.Integer(), nullable=True, server_default="1"
        ),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["transcript_segment_id"], ["transcript_segments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )

    # Create indexes for transcript_sentences
    op.create_index(
        "idx_sentence_segment", "transcript_sentences", ["transcript_segment_id"]
    )
    op.create_index("idx_sentence_speaker", "transcript_sentences", ["speaker_id"])
    op.create_index(
        "idx_sentence_time",
        "transcript_sentences",
        ["transcript_segment_id", "start_time"],
    )
    op.create_index(
        "idx_sentence_analysis_run", "transcript_sentences", ["analysis_run_id"]
    )

    # Create speaker_vocabulary_words table
    op.create_table(
        "speaker_vocabulary_words",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("tfidf_score", sa.Float(), nullable=False),
        sa.Column("term_frequency", sa.Integer(), nullable=True, server_default="0"),
        sa.Column(
            "document_frequency", sa.Integer(), nullable=True, server_default="0"
        ),
        sa.Column(
            "ngram_type", sa.String(length=20), nullable=True, server_default="unigram"
        ),
        sa.Column("source_transcript_file_id", sa.Integer(), nullable=True),
        sa.Column("vectorizer_params_hash", sa.String(length=64), nullable=False),
        sa.Column("source_window", sa.String(length=50), nullable=True),
        sa.Column("snapshot_version", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_transcript_file_id"], ["transcript_files.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint(
            "speaker_id",
            "word",
            "ngram_type",
            "source_transcript_file_id",
            "snapshot_version",
            name="uq_speaker_word_ngram_snapshot",
        ),
    )

    # Create indexes for speaker_vocabulary_words
    op.create_index(
        "idx_vocab_speaker_word", "speaker_vocabulary_words", ["speaker_id", "word"]
    )
    op.create_index("idx_vocab_word", "speaker_vocabulary_words", ["word"])
    op.create_index("idx_vocab_tfidf", "speaker_vocabulary_words", ["tfidf_score"])
    op.create_index(
        "idx_vocab_snapshot",
        "speaker_vocabulary_words",
        ["speaker_id", "source_transcript_file_id", "snapshot_version"],
    )
    op.create_index(
        "idx_vocab_analysis_run", "speaker_vocabulary_words", ["analysis_run_id"]
    )
    op.create_index(
        "idx_vocab_vectorizer_params",
        "speaker_vocabulary_words",
        ["vectorizer_params_hash"],
    )

    # Create speaker_resolution_events table
    op.create_table(
        "speaker_resolution_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transcript_file_id", sa.Integer(), nullable=False),
        sa.Column("speaker_id", sa.Integer(), nullable=True),
        sa.Column("diarized_label", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["transcript_file_id"], ["transcript_files.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for speaker_resolution_events
    op.create_index(
        "idx_resolution_event_file", "speaker_resolution_events", ["transcript_file_id"]
    )
    op.create_index(
        "idx_resolution_event_speaker", "speaker_resolution_events", ["speaker_id"]
    )
    op.create_index(
        "idx_resolution_event_method", "speaker_resolution_events", ["method"]
    )
    op.create_index(
        "idx_resolution_event_unresolved",
        "speaker_resolution_events",
        ["transcript_file_id", "speaker_id"],
    )
    op.create_index(
        "idx_resolution_event_analysis_run",
        "speaker_resolution_events",
        ["analysis_run_id"],
    )
    op.create_index(
        "idx_resolution_event_created", "speaker_resolution_events", ["created_at"]
    )
    op.create_index(
        "idx_resolution_event_diarized_label",
        "speaker_resolution_events",
        ["diarized_label"],
    )


def downgrade():
    """Remove sentence storage, vocabulary storage, and resolution event tables."""

    # Drop indexes
    op.drop_index(
        "idx_resolution_event_diarized_label", table_name="speaker_resolution_events"
    )
    op.drop_index(
        "idx_resolution_event_created", table_name="speaker_resolution_events"
    )
    op.drop_index(
        "idx_resolution_event_analysis_run", table_name="speaker_resolution_events"
    )
    op.drop_index(
        "idx_resolution_event_unresolved", table_name="speaker_resolution_events"
    )
    op.drop_index("idx_resolution_event_method", table_name="speaker_resolution_events")
    op.drop_index(
        "idx_resolution_event_speaker", table_name="speaker_resolution_events"
    )
    op.drop_index("idx_resolution_event_file", table_name="speaker_resolution_events")

    op.drop_index("idx_vocab_vectorizer_params", table_name="speaker_vocabulary_words")
    op.drop_index("idx_vocab_analysis_run", table_name="speaker_vocabulary_words")
    op.drop_index("idx_vocab_snapshot", table_name="speaker_vocabulary_words")
    op.drop_index("idx_vocab_tfidf", table_name="speaker_vocabulary_words")
    op.drop_index("idx_vocab_word", table_name="speaker_vocabulary_words")
    op.drop_index("idx_vocab_speaker_word", table_name="speaker_vocabulary_words")

    op.drop_index("idx_sentence_analysis_run", table_name="transcript_sentences")
    op.drop_index("idx_sentence_time", table_name="transcript_sentences")
    op.drop_index("idx_sentence_speaker", table_name="transcript_sentences")
    op.drop_index("idx_sentence_segment", table_name="transcript_sentences")

    # Drop tables
    op.drop_table("speaker_resolution_events")
    op.drop_table("speaker_vocabulary_words")
    op.drop_table("transcript_sentences")
