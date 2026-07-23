"""Single-ownership constants for llm_custom_qa."""

from __future__ import annotations

SCHEMA_ID = "transcriptx.llm_custom_qa.v1"
PROMPT_VERSION = "1"
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

MAX_RETRY_ATTEMPTS = 3

CONFIG_LOCK_TIMEOUT_SECONDS = 5.0
