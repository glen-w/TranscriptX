"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class KeyphrasesConfig:
    """Keyphrases settings. Defaults owned by KeyphrasesSettingsModel."""

    enabled_methods: list = field(init=False, repr=True)
    max_phrases: int = field(init=False, repr=True)
    min_phrase_tokens: int = field(init=False, repr=True)
    max_phrase_tokens: int = field(init=False, repr=True)
    min_occurrences_global: int = field(init=False, repr=True)
    min_occurrences_speaker: int = field(init=False, repr=True)
    diversity_jaccard_threshold: float = field(init=False, repr=True)
    evidence_max_per_phrase: int = field(init=False, repr=True)
    evidence_snippet_max_chars: int = field(init=False, repr=True)
    keybert_model_id: str = field(init=False, repr=True)
    yake_lan: str = field(init=False, repr=True)
    yake_n: int = field(init=False, repr=True)
    yake_top: int = field(init=False, repr=True)
    yake_window_size: int = field(init=False, repr=True)
    min_member_sessions: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.keyphrases import KeyphrasesSettingsModel

        _hydrate_dataclass_from_pydantic(self, KeyphrasesSettingsModel())
