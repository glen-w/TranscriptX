"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic

from .analysis_corrections_llm import CorrectionsLlmConfig


@dataclass
class CorrectionsConfig:
    """Configuration for transcript corrections. Defaults owned by CorrectionsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    interactive_review: bool = field(init=False, repr=True)
    consistency_similarity_threshold: float = field(init=False, repr=True)
    fuzzy_similarity_threshold: float = field(init=False, repr=True)
    known_acronyms: list[str] = field(init=False, repr=True)
    known_org_phrases: dict[str, list[str]] = field(init=False, repr=True)
    write_csv_summary: bool = field(init=False, repr=True)
    store_corrected_transcript: bool = field(init=False, repr=True)
    default_rule_scope: str = field(init=False, repr=True)
    enable_fuzzy: bool = field(init=False, repr=True)
    update_original_file: bool = field(init=False, repr=True)
    create_backup: bool = field(init=False, repr=True)
    llm: CorrectionsLlmConfig = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.corrections import CorrectionsSettingsModel

        _hydrate_dataclass_from_pydantic(self, CorrectionsSettingsModel())
