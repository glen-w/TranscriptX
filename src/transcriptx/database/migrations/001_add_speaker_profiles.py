"""
Migration: Add speaker profile tables.

This migration adds the new speaker profile tables for storing comprehensive
speaker analysis data including sentiment, emotion, topic, entity, tic,
semantic, interaction, and performance profiles.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_add_speaker_profiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add speaker profile tables."""

    # Create speaker_sentiment_profiles table
    op.create_table(
        "speaker_sentiment_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("average_sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_volatility", sa.Float(), nullable=True),
        sa.Column("dominant_sentiment_pattern", sa.String(length=50), nullable=True),
        sa.Column("sentiment_trends", sa.JSON(), nullable=True),
        sa.Column("positive_trigger_words", sa.JSON(), nullable=True),
        sa.Column("negative_trigger_words", sa.JSON(), nullable=True),
        sa.Column("sentiment_consistency_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_sentiment_profiles
    op.create_index(
        "idx_sentiment_profile_score",
        "speaker_sentiment_profiles",
        ["average_sentiment_score"],
    )
    op.create_index(
        "idx_sentiment_profile_volatility",
        "speaker_sentiment_profiles",
        ["sentiment_volatility"],
    )
    op.create_index(
        "idx_sentiment_profile_consistency",
        "speaker_sentiment_profiles",
        ["sentiment_consistency_score"],
    )

    # Create speaker_emotion_profiles table
    op.create_table(
        "speaker_emotion_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("dominant_emotion", sa.String(length=50), nullable=True),
        sa.Column("emotion_distribution", sa.JSON(), nullable=True),
        sa.Column("emotional_stability", sa.Float(), nullable=True),
        sa.Column("emotion_transition_patterns", sa.JSON(), nullable=True),
        sa.Column("emotional_reactivity", sa.Float(), nullable=True),
        sa.Column("emotion_consistency", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_emotion_profiles
    op.create_index(
        "idx_emotion_profile_dominant", "speaker_emotion_profiles", ["dominant_emotion"]
    )
    op.create_index(
        "idx_emotion_profile_stability",
        "speaker_emotion_profiles",
        ["emotional_stability"],
    )
    op.create_index(
        "idx_emotion_profile_reactivity",
        "speaker_emotion_profiles",
        ["emotional_reactivity"],
    )
    op.create_index(
        "idx_emotion_profile_consistency",
        "speaker_emotion_profiles",
        ["emotion_consistency"],
    )

    # Create speaker_topic_profiles table
    op.create_table(
        "speaker_topic_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("preferred_topics", sa.JSON(), nullable=True),
        sa.Column("topic_expertise_scores", sa.JSON(), nullable=True),
        sa.Column("topic_contribution_patterns", sa.JSON(), nullable=True),
        sa.Column("topic_engagement_style", sa.String(length=50), nullable=True),
        sa.Column("topic_evolution_trends", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_topic_profiles
    op.create_index(
        "idx_topic_profile_engagement",
        "speaker_topic_profiles",
        ["topic_engagement_style"],
    )

    # Create speaker_entity_profiles table
    op.create_table(
        "speaker_entity_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("entity_expertise_domains", sa.JSON(), nullable=True),
        sa.Column("frequently_mentioned_entities", sa.JSON(), nullable=True),
        sa.Column("entity_network", sa.JSON(), nullable=True),
        sa.Column("entity_sentiment_patterns", sa.JSON(), nullable=True),
        sa.Column("entity_evolution", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create speaker_tic_profiles table
    op.create_table(
        "speaker_tic_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("tic_frequency", sa.JSON(), nullable=True),
        sa.Column("tic_types", sa.JSON(), nullable=True),
        sa.Column("tic_context_patterns", sa.JSON(), nullable=True),
        sa.Column("tic_evolution", sa.JSON(), nullable=True),
        sa.Column("tic_reduction_goals", sa.JSON(), nullable=True),
        sa.Column("tic_confidence_indicators", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create speaker_semantic_profiles table
    op.create_table(
        "speaker_semantic_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("semantic_fingerprint", sa.JSON(), nullable=True),
        sa.Column("vocabulary_sophistication", sa.Float(), nullable=True),
        sa.Column("semantic_consistency", sa.Float(), nullable=True),
        sa.Column("agreement_patterns", sa.JSON(), nullable=True),
        sa.Column("disagreement_patterns", sa.JSON(), nullable=True),
        sa.Column("semantic_evolution", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_semantic_profiles
    op.create_index(
        "idx_semantic_profile_sophistication",
        "speaker_semantic_profiles",
        ["vocabulary_sophistication"],
    )
    op.create_index(
        "idx_semantic_profile_consistency",
        "speaker_semantic_profiles",
        ["semantic_consistency"],
    )

    # Create speaker_interaction_profiles table
    op.create_table(
        "speaker_interaction_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("interaction_style", sa.String(length=50), nullable=True),
        sa.Column("interruption_patterns", sa.JSON(), nullable=True),
        sa.Column("response_patterns", sa.JSON(), nullable=True),
        sa.Column("interaction_network", sa.JSON(), nullable=True),
        sa.Column("influence_score", sa.Float(), nullable=True),
        sa.Column("collaboration_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_interaction_profiles
    op.create_index(
        "idx_interaction_profile_style",
        "speaker_interaction_profiles",
        ["interaction_style"],
    )
    op.create_index(
        "idx_interaction_profile_influence",
        "speaker_interaction_profiles",
        ["influence_score"],
    )
    op.create_index(
        "idx_interaction_profile_collaboration",
        "speaker_interaction_profiles",
        ["collaboration_score"],
    )

    # Create speaker_performance_profiles table
    op.create_table(
        "speaker_performance_profiles",
        sa.Column("speaker_id", sa.Integer(), nullable=False),
        sa.Column("speaking_style", sa.String(length=50), nullable=True),
        sa.Column("participation_patterns", sa.JSON(), nullable=True),
        sa.Column("performance_metrics", sa.JSON(), nullable=True),
        sa.Column("improvement_areas", sa.JSON(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
        ),
        sa.PrimaryKeyConstraint("speaker_id"),
    )

    # Create indexes for speaker_performance_profiles
    op.create_index(
        "idx_performance_profile_style",
        "speaker_performance_profiles",
        ["speaking_style"],
    )


def downgrade():
    """Remove speaker profile tables."""

    # Drop speaker_performance_profiles table
    op.drop_index(
        "idx_performance_profile_style", table_name="speaker_performance_profiles"
    )
    op.drop_table("speaker_performance_profiles")

    # Drop speaker_interaction_profiles table
    op.drop_index(
        "idx_interaction_profile_collaboration",
        table_name="speaker_interaction_profiles",
    )
    op.drop_index(
        "idx_interaction_profile_influence", table_name="speaker_interaction_profiles"
    )
    op.drop_index(
        "idx_interaction_profile_style", table_name="speaker_interaction_profiles"
    )
    op.drop_table("speaker_interaction_profiles")

    # Drop speaker_semantic_profiles table
    op.drop_index(
        "idx_semantic_profile_consistency", table_name="speaker_semantic_profiles"
    )
    op.drop_index(
        "idx_semantic_profile_sophistication", table_name="speaker_semantic_profiles"
    )
    op.drop_table("speaker_semantic_profiles")

    # Drop speaker_tic_profiles table
    op.drop_table("speaker_tic_profiles")

    # Drop speaker_entity_profiles table
    op.drop_table("speaker_entity_profiles")

    # Drop speaker_topic_profiles table
    op.drop_index("idx_topic_profile_engagement", table_name="speaker_topic_profiles")
    op.drop_table("speaker_topic_profiles")

    # Drop speaker_emotion_profiles table
    op.drop_index(
        "idx_emotion_profile_consistency", table_name="speaker_emotion_profiles"
    )
    op.drop_index(
        "idx_emotion_profile_reactivity", table_name="speaker_emotion_profiles"
    )
    op.drop_index(
        "idx_emotion_profile_stability", table_name="speaker_emotion_profiles"
    )
    op.drop_index("idx_emotion_profile_dominant", table_name="speaker_emotion_profiles")
    op.drop_table("speaker_emotion_profiles")

    # Drop speaker_sentiment_profiles table
    op.drop_index(
        "idx_sentiment_profile_consistency", table_name="speaker_sentiment_profiles"
    )
    op.drop_index(
        "idx_sentiment_profile_volatility", table_name="speaker_sentiment_profiles"
    )
    op.drop_index(
        "idx_sentiment_profile_score", table_name="speaker_sentiment_profiles"
    )
    op.drop_table("speaker_sentiment_profiles")
