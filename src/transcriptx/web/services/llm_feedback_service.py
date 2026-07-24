"""Resolve an injected LLM feedback service for Streamlit pages/blocks."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from transcriptx.core.llm_feedback.service import LlmFeedbackService
from transcriptx.core.utils.paths import DATA_DIR


def get_llm_feedback_service(
    *, data_dir: Path | str | None = None
) -> LlmFeedbackService:
    """Build service with resolved data_dir (outside the feedback widget)."""
    root = Path(data_dir) if data_dir is not None else Path(DATA_DIR)
    return _cached_service(str(root.resolve()))


@lru_cache(maxsize=4)
def _cached_service(data_dir: str) -> LlmFeedbackService:
    # Cached factory only — never cache submit results.
    return LlmFeedbackService(data_dir=data_dir)


def clear_llm_feedback_service_cache() -> None:
    _cached_service.cache_clear()
