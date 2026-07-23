"""Single-ownership constants for llm_custom_qa."""

from __future__ import annotations

SCHEMA_ID = "transcriptx.llm_custom_qa.v1"
PROMPT_VERSION = "2"
MODULE_VERSION = "1"
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
