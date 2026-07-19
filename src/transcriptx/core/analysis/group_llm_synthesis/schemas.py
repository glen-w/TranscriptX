"""Versioned schema IDs and prompt versions for group LLM synthesis."""

from __future__ import annotations

from typing import Literal

SCHEMA_GLOBAL = "transcriptx.group_llm_summary.v1"
SCHEMA_SPEAKER_INDEX = "transcriptx.group_llm_speaker_summary_index.v1"
SCHEMA_SPEAKER = "transcriptx.group_llm_speaker_summary.v1"
SCHEMA_OUTCOME = "transcriptx.group_llm_synthesis_outcome.v1"
SCHEMA_ACTIVE = "transcriptx.group_llm_synthesis_active.v1"
SCHEMA_COMMIT = "transcriptx.group_llm_synthesis_commit.v1"

COLLECT_BLOB_AGGREGATION_KEY = "llm_summary"
COLLECT_SCHEMA_VERSION = 1

GROUP_LLM_SUMMARY_PROMPT_VERSION = "1"
GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION = "1"

UnitStatus = Literal["success", "failed", "skipped"]
OverallStatus = Literal["success", "partial", "failed", "skipped"]
AttemptStatus = Literal[
    "success",
    "partial",
    "failed",
    "skipped",
    "cancelled",
    "lock_timeout",
]

MAX_SPEAKERS = 32
MAX_SUMMARY_CHARS = 64 * 1024
METADATA_SAMPLE_K = 16
SAFE_ERROR_MESSAGE_MAX = 240
EMPTY_FILE_SENTINEL = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
LOCK_TIMEOUT_SECONDS = 30.0

SYNTHESIS_ROOT_NAME = ".group_llm_synthesis"
ACTIVE_FILENAME = "ACTIVE.json"
COMMIT_FILENAME = "COMMIT.json"
OUTCOME_FILENAME = "outcome.json"
GENERATIONS_DIRNAME = "generations"
LOCK_FILENAME = ".lock"
