"""Versioned schema IDs and constants for chart LLM descriptions."""

from __future__ import annotations

from typing import Literal

SCHEMA_DESCRIPTION = "transcriptx.chart_description.v1"
SCHEMA_INDEX = "transcriptx.chart_descriptions_index.v1"
SCHEMA_OUTCOME = "transcriptx.chart_descriptions_outcome.v1"
SCHEMA_ACTIVE = "transcriptx.chart_descriptions_active.v1"
SCHEMA_COMMIT = "transcriptx.chart_descriptions_commit.v1"
SCHEMA_ATTEMPT = "transcriptx.chart_descriptions_attempt.v1"
SCHEMA_EVIDENCE = "transcriptx.chart_evidence.v1"
SCHEMA_LOGICAL_INVENTORY = "transcriptx.logical_chart_inventory.v1"

CHART_DESCRIPTIONS_PROMPT_VERSION = "1"

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

SAFE_ERROR_MESSAGE_MAX = 240
DEFAULT_MAX_DESCRIPTION_CHARS = 1200
MAX_EVIDENCE_BYTES = 48 * 1024
MAX_EVIDENCE_LABELS = 64
MAX_EVIDENCE_VALUES = 256
LOCK_TIMEOUT_SECONDS = 30.0

ROOT_NAME = ".chart_descriptions"
ACTIVE_FILENAME = "ACTIVE.json"
ATTEMPT_FILENAME = "LATEST_ATTEMPT.json"
COMMIT_FILENAME = "COMMIT.json"
OUTCOME_FILENAME = "outcome.json"
INDEX_FILENAME = "index.json"
GENERATIONS_DIRNAME = "generations"
LOCK_FILENAME = ".lock"
MODULE_ID = "chart_descriptions"
