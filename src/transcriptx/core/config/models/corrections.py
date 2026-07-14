"""Pydantic schema for analysis.corrections."""

from pydantic import BaseModel, Field

from transcriptx.core.config.models.corrections_llm import CorrectionsLlmSettingsModel


class CorrectionsKnownOrgPhrasesModel(BaseModel):
    REN21: list[str] = Field(
        default_factory=lambda: ["ren twenty one", "wren twenty one"]
    )


class CorrectionsSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    interactive_review: bool = Field(default=True)
    consistency_similarity_threshold: float = Field(default=0.88)
    fuzzy_similarity_threshold: float = Field(default=0.92)
    known_acronyms: list[str] = Field(default_factory=lambda: ["CSE", "REN21"])
    known_org_phrases: CorrectionsKnownOrgPhrasesModel = Field(
        default_factory=CorrectionsKnownOrgPhrasesModel
    )
    write_csv_summary: bool = Field(default=True)
    store_corrected_transcript: bool = Field(default=True)
    default_rule_scope: str = Field(default="project")
    enable_fuzzy: bool = Field(default=False)
    update_original_file: bool = Field(default=False)
    create_backup: bool = Field(default=True)
    llm: CorrectionsLlmSettingsModel = Field(
        default_factory=CorrectionsLlmSettingsModel
    )
