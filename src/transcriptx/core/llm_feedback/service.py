"""Facade for recording LLM output feedback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.core.llm_feedback.models import (
    FeedbackEvent,
    FeedbackProvenance,
    FeedbackRating,
    FeedbackReason,
    FeedbackTarget,
    build_event,
)
from transcriptx.core.llm_feedback.store import AppendResult, FeedbackStore, IterEventsResult
from transcriptx.core.utils.paths import DATA_DIR


class LlmFeedbackService:
    """Thin service wrapping :class:`FeedbackStore` for web/API callers."""

    def __init__(
        self,
        store: FeedbackStore | None = None,
        *,
        data_dir: Path | str | None = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            root = Path(data_dir) if data_dir is not None else Path(DATA_DIR)
            self._store = FeedbackStore(root)

    @property
    def store(self) -> FeedbackStore:
        return self._store

    def submit(
        self,
        *,
        rating: FeedbackRating | str,
        reason: FeedbackReason | str,
        note: str,
        output_text: str,
        target: FeedbackTarget,
        provenance: FeedbackProvenance | None = None,
        submission_token: str,
        supersedes_feedback_id: str | None = None,
    ) -> AppendResult:
        event = build_event(
            rating=rating,
            reason=reason,
            note=note,
            output_text=output_text,
            target=target,
            provenance=provenance,
            submission_token=submission_token,
            supersedes_feedback_id=supersedes_feedback_id,
        )
        return self._store.append(event)

    def append_event(self, event: FeedbackEvent | dict[str, Any]) -> AppendResult:
        return self._store.append(event)

    def iter_events(self) -> IterEventsResult:
        return self._store.iter_events()

    def latest_for_instance(self, target_instance_id: str) -> str | None:
        return self._store.latest_feedback_id_for_instance(target_instance_id)
