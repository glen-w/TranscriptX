"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class LLMCustomQAConfig:
    """Defaults owned by LLMCustomQASettingsModel."""

    effort: str = field(init=False, repr=True)
    saved_questions: list = field(init=False, repr=True)
    evidence_pack_ids: object = field(init=False, repr=True)
    include_transcript: bool = field(init=False, repr=True)
    routing_enabled: bool = field(init=False, repr=True)
    max_packs_per_question: int = field(init=False, repr=True)
    max_reasoning_chars: int = field(init=False, repr=True)
    max_eligible_speakers: int = field(init=False, repr=True)
    max_speaker_question_cells: int = field(init=False, repr=True)
    max_llm_calls_per_run: int = field(init=False, repr=True)
    max_library_questions: int = field(init=False, repr=True)
    max_library_total_question_chars: int = field(init=False, repr=True)
    max_questions_per_run: int = field(init=False, repr=True)
    max_question_chars: int = field(init=False, repr=True)
    max_run_total_question_chars: int = field(init=False, repr=True)
    max_answer_chars: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_custom_qa import (
            LLMCustomQASettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LLMCustomQASettingsModel())
