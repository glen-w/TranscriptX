"""Workflow configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .analysis import (
    _hydrate_analysis_slice,
    _hydrate_dataclass_from_pydantic,
)


@dataclass
class SpeakerGateConfig:
    """Defaults owned by SpeakerGateSettingsModel (nested under workflow)."""

    threshold_value: float = field(init=False, repr=True)
    threshold_type: Literal["absolute", "percentage"] = field(init=False, repr=True)
    mode: Literal["ignore", "warn", "enforce"] = field(init=False, repr=True)
    exemplar_count: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.workflow import SpeakerGateSettingsModel

        _hydrate_dataclass_from_pydantic(self, SpeakerGateSettingsModel())
        self.validate()

    def validate(self) -> None:
        """Normalize and validate speaker gate settings (warn + default on invalid)."""
        from transcriptx.core.utils.logger import log_warning

        threshold_type = str(self.threshold_type).strip().lower()
        if threshold_type not in ("absolute", "percentage"):
            log_warning(
                "CONFIG",
                f"Invalid speaker_gate.threshold_type '{self.threshold_type}', using 'absolute'",
            )
            threshold_type = "absolute"
        self.threshold_type = threshold_type  # type: ignore[assignment]

        mode = str(self.mode).strip().lower()
        if mode not in ("ignore", "warn", "enforce"):
            log_warning(
                "CONFIG",
                f"Invalid speaker_gate.mode '{self.mode}', using 'warn'",
            )
            mode = "warn"
        self.mode = mode  # type: ignore[assignment]

        try:
            threshold_value = float(self.threshold_value)
        except (TypeError, ValueError):
            log_warning(
                "CONFIG",
                f"Invalid speaker_gate.threshold_value '{self.threshold_value}', using 0.0",
            )
            threshold_value = 0.0

        if threshold_value < 0.0:
            log_warning(
                "CONFIG",
                f"speaker_gate.threshold_value {threshold_value} < 0; clamping to 0.0",
            )
            threshold_value = 0.0

        if self.threshold_type == "percentage" and threshold_value > 100.0:
            log_warning(
                "CONFIG",
                f"speaker_gate.threshold_value {threshold_value} > 100; clamping to 100.0",
            )
            threshold_value = 100.0
        self.threshold_value = threshold_value

        try:
            exemplar_count = int(self.exemplar_count)
        except (TypeError, ValueError):
            log_warning(
                "CONFIG",
                f"Invalid speaker_gate.exemplar_count '{self.exemplar_count}', using 0",
            )
            exemplar_count = 0

        if exemplar_count < 0:
            log_warning(
                "CONFIG",
                f"speaker_gate.exemplar_count {exemplar_count} < 0; clamping to 0",
            )
            exemplar_count = 0
        self.exemplar_count = exemplar_count


@dataclass
class WorkflowConfig:
    """Defaults owned by WorkflowSettingsModel."""

    timeout_quick_seconds: int = field(init=False, repr=True)
    timeout_full_seconds: int = field(init=False, repr=True)
    update_interval: float = field(init=False, repr=True)
    max_size_mb: int = field(init=False, repr=True)
    subprocess_timeout: int = field(init=False, repr=True)
    mp3_bitrate: str = field(init=False, repr=True)
    conversion_time_factor: float = field(init=False, repr=True)
    speaker_gate: SpeakerGateConfig = field(init=False, repr=True)
    cli_pruning_enabled: bool = field(init=False, repr=True)
    default_config_save_path: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.workflow import (
            WorkflowSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, WorkflowSettingsModel())


@dataclass
class InputConfig:
    """Defaults owned by InputSettingsModel."""

    wav_folders: list[str] = field(init=False, repr=True)
    recordings_folders: list[str] = field(init=False, repr=True)
    prefill_rename_with_date_prefix: bool = field(init=False, repr=True)
    file_selection_mode: Literal["prompt", "explore", "direct"] = field(
        init=False, repr=True
    )
    playback_skip_seconds_short: float = field(init=False, repr=True)
    playback_skip_seconds_long: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.input import (
            InputSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, InputSettingsModel())


@dataclass
class OutputConfig:
    """Defaults owned by OutputSettingsModel."""

    base_output_dir: str = field(init=False, repr=True)
    create_subdirectories: bool = field(init=False, repr=True)
    overwrite_existing: bool = field(init=False, repr=True)
    dynamic_charts: Literal["auto", "on", "off"] = field(init=False, repr=True)
    dynamic_views: Literal["auto", "on", "off"] = field(init=False, repr=True)
    default_audio_folder: str = field(init=False, repr=True)
    default_transcript_folder: str = field(init=False, repr=True)
    default_readable_transcript_folder: str = field(init=False, repr=True)
    audio_deduplication_threshold: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.output import (
            OutputSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, OutputSettingsModel())


@dataclass
class GroupAnalysisConfig:
    """Defaults owned by GroupAnalysisSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    output_dir: str = field(init=False, repr=True)
    persist_groups: bool = field(init=False, repr=True)
    enable_stats_aggregation: bool = field(init=False, repr=True)
    scaffold_by_session: bool = field(init=False, repr=True)
    scaffold_by_speaker: bool = field(init=False, repr=True)
    scaffold_comparisons: bool = field(init=False, repr=True)
    wordcloud_pooled_emit_full_transcript_global: bool = field(init=False, repr=True)
    wordcloud_pooled_global_tfidf: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.group_analysis import (
            GroupAnalysisSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, GroupAnalysisSettingsModel())


@dataclass
class MetadataConfig:
    """Defaults owned by MetadataSettingsModel."""

    duration_calculation: Literal["max_end", "span"] = field(init=False, repr=True)
    listing_word_count_fallback: Literal["in_memory", "metadata_only"] = field(
        init=False, repr=True
    )
    auto_refresh_on_write: bool = field(init=False, repr=True)
    legacy_words_alias: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.metadata import (
            MetadataSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, MetadataSettingsModel())


@dataclass
class DashboardConfig:
    """Defaults owned by dashboard_display + dashboard_overview pilots."""

    schema_version: int = field(init=False, repr=True)
    overview_charts: list[str] = field(init=False, repr=True)
    overview_missing_behavior: str = field(init=False, repr=True)
    overview_max_items: int | None = field(init=False, repr=True)
    duration_hours_threshold_seconds: int = field(init=False, repr=True)
    duration_summary_style: Literal["compact", "minutes_only"] = field(
        init=False, repr=True
    )
    transcript_exclude_unnamed_speakers: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.dashboard_display import (
            DashboardDisplaySettingsModel,
        )
        from transcriptx.core.config.models.dashboard_overview import (
            DashboardOverviewSettingsModel,
        )

        # Fixed order: display then overview (disjoint field sets).
        _hydrate_analysis_slice(self, DashboardDisplaySettingsModel())
        _hydrate_analysis_slice(self, DashboardOverviewSettingsModel())
