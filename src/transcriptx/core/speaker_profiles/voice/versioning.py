"""Frozen schema identities and path constants for speaker-profile voice phase."""

from __future__ import annotations

VOICE_SCHEMA_VERSION = 1

VOICE_SUBTREE = "voice"

PRIVACY_SETTINGS_SCHEMA_ID = "voice_privacy_settings.v1"
PRIVACY_SETTINGS_FILENAME = "privacy.voice_settings.json"

ACTIVE_GENERATION_SCHEMA_ID = "voice_active_generation.v1"
ACTIVE_GENERATION_FILENAME = "active_generation.json"

MODEL_GENERATION_SCHEMA_ID = "voice_model_generation.v1"
VOICE_SAMPLE_SCHEMA_ID = "voice_sample.v1"
VOICE_EMBEDDING_SCHEMA_ID = "voice_embedding.v1"
VOICE_DECISION_SCHEMA_ID = "voice_match_decision.v1"
VOICE_SUGGESTION_SCHEMA_ID = "voice_match_suggestion.v1"
PROFILE_VOICE_SUMMARY_SCHEMA_ID = "profile_voice_summary.v1"

VOICE_SAMPLE_FILE_SUFFIX = ".voice_sample.json"
VOICE_EMBEDDING_FILE_SUFFIX = ".voice_embedding.json"
VOICE_DECISION_FILE_SUFFIX = ".voice_decision.json"

PREPROCESSING_POLICY_ID = "voice_preprocess.v1"
QUALITY_POLICY_ID = "voice_quality.v1"
THRESHOLD_POLICY_ID = "voice_threshold.v1"
EMBEDDING_SCHEMA_VERSION = "voice_embedding_vector.v1"

# Content-addressed sample / embedding id prefixes
SAMPLE_ID_PREFIX = "voice_sample_id.v1"
EMBEDDING_ID_PREFIX = "voice_embedding_id.v1"

# Flip only when Stage 8 exit criteria are met (see ActivationBarrier).
FEATURE_GATE_COMPLETE = True
