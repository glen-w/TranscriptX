"""Single-ownership constants for llm_custom_qa."""

from __future__ import annotations

from transcriptx.core.analysis.llm_custom_qa.versioning import (
    COMMIT_MARKER_SCHEMA_VERSION,
    COMMIT_MARKER_SCHEMA_VERSION_V1,
    COMMIT_MARKER_SCHEMA_VERSION_V2,
    V1_CONTRACT_VERSION,
    V1_MODULE_VERSION,
    V1_SCHEMA_ID,
    V2_CONTRACT_VERSION,
    V2_MODULE_VERSION,
    V2_SCHEMA_ID,
    custom_qa_execution_branch,
    get_custom_qa_activation,
    is_v2_execution_enabled,
    live_module_version_for_writers,
    live_schema_id_for_writers,
    set_custom_qa_activation,
)

# Live writer aliases — selected by activation for *new* runs only.
# Historical validators must import V1_* / V2_* from versioning, not these.


def __getattr__(name: str) -> str:
    if name == "SCHEMA_ID":
        return live_schema_id_for_writers()
    if name == "MODULE_VERSION":
        return live_module_version_for_writers()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


PROMPT_VERSION = "2"
MODULE_NAME = "llm_custom_qa"
ABSENCE_DETECTOR_VERSION = "1"

# Analysis-layer SoT. Config model Field default must stay equal (parity test);
# config.models cannot import analysis, and analysis cannot import config.models.
MAX_ANSWER_CHARS = 800

MAX_CITATIONS_PER_ANSWER = 3
MAX_QUOTES_FROM_MODEL = 3
MAX_CROSS_SEGMENT_SPAN = 3
GROUNDING_SEGMENT_SEPARATOR = "\n"
# When a model paraphrase fails full-quote match, keep the longest grounded
# contiguous word span (≥ this many words) as the citation.
MIN_RECOVERED_QUOTE_WORDS = 6

# Effort profiles allow huge inputs for summaries; cite-or-unavailable QA needs a
# tighter window so mid-size local models (e.g. mistral-nemo) can copy quotes and
# emit one row per question. Applied as min(effort_budget, this cap).
MAX_CUSTOM_QA_CORPUS_CHARS = 24_000

MAX_RETRY_ATTEMPTS = 3
# Extra generation after incomplete/ungrounded rows (separate from transport retries).
MAX_QUALITY_RETRY_ATTEMPTS = 1

CONFIG_LOCK_TIMEOUT_SECONDS = 5.0

# Cardinality / cost defaults (Stage 0 freeze).
MAX_ELIGIBLE_SPEAKERS_DEFAULT = 12
MAX_SPEAKER_QUESTION_CELLS_DEFAULT = 48
MAX_LLM_CALLS_PER_RUN_DEFAULT = 16
MAX_PACKS_PER_QUESTION_DEFAULT = 3
MAX_REASONING_CHARS_DEFAULT = 600

__all__ = [
    "ABSENCE_DETECTOR_VERSION",
    "COMMIT_MARKER_SCHEMA_VERSION",
    "COMMIT_MARKER_SCHEMA_VERSION_V1",
    "COMMIT_MARKER_SCHEMA_VERSION_V2",
    "CONFIG_LOCK_TIMEOUT_SECONDS",
    "GROUNDING_SEGMENT_SEPARATOR",
    "MAX_ANSWER_CHARS",
    "MAX_CITATIONS_PER_ANSWER",
    "MAX_CROSS_SEGMENT_SPAN",
    "MAX_CUSTOM_QA_CORPUS_CHARS",
    "MAX_ELIGIBLE_SPEAKERS_DEFAULT",
    "MAX_LLM_CALLS_PER_RUN_DEFAULT",
    "MAX_PACKS_PER_QUESTION_DEFAULT",
    "MAX_QUALITY_RETRY_ATTEMPTS",
    "MAX_QUOTES_FROM_MODEL",
    "MAX_REASONING_CHARS_DEFAULT",
    "MAX_RETRY_ATTEMPTS",
    "MAX_SPEAKER_QUESTION_CELLS_DEFAULT",
    "MIN_RECOVERED_QUOTE_WORDS",
    "MODULE_NAME",
    "MODULE_VERSION",
    "PROMPT_VERSION",
    "SCHEMA_ID",
    "V1_CONTRACT_VERSION",
    "V1_MODULE_VERSION",
    "V1_SCHEMA_ID",
    "V2_CONTRACT_VERSION",
    "V2_MODULE_VERSION",
    "V2_SCHEMA_ID",
    "custom_qa_execution_branch",
    "get_custom_qa_activation",
    "is_v2_execution_enabled",
    "live_module_version_for_writers",
    "live_schema_id_for_writers",
    "set_custom_qa_activation",
]
