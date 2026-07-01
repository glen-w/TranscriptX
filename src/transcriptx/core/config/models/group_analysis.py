"""Pydantic schema for group_analysis."""

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR


class GroupAnalysisSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    output_dir: str = Field(default_factory=lambda: str(GROUP_OUTPUTS_DIR))
    persist_groups: bool = Field(default=False)
    enable_stats_aggregation: bool = Field(default=True)
    scaffold_by_session: bool = Field(default=True)
    scaffold_by_speaker: bool = Field(default=True)
    scaffold_comparisons: bool = Field(default=True)
    wordcloud_pooled_emit_full_transcript_global: bool = Field(default=False)
    wordcloud_pooled_global_tfidf: bool = Field(default=False)
