"""Frozen schema identities for speaker_profiles v1."""

from __future__ import annotations

SCHEMA_VERSION = 1

PROFILE_SCHEMA_ID = "speaker_profile.v1"
LINK_SCHEMA_ID = "speaker_profile_link.v1"
EVENT_SCHEMA_ID = "speaker_profile_event.v1"
OPERATION_SCHEMA_ID = "speaker_profile_operation.v1"

OCCURRENCE_KEY_PREFIX = "speaker_occurrence_key.v1"
OCCURRENCE_FINGERPRINT_PREFIX = "occurrence_fingerprint.v1"

PROFILE_FILE_SUFFIX = ".speaker_profile.json"
LINK_FILE_SUFFIX = ".speaker_link.json"
EVENT_FILE_SUFFIX = ".speaker_event.json"
OPERATION_FILE_SUFFIX = ".op.json"

PROJECT_LOCK_NAME = "speaker_profiles.lock"
