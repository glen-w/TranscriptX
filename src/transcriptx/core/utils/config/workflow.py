"""Workflow configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
from transcriptx.core.utils.paths import (  # type: ignore[import-untyped]
    RECORDINGS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    DIARISED_TRANSCRIPTS_DIR,
    OUTPUTS_DIR,
    GROUP_OUTPUTS_DIR,
)


@dataclass
class SpeakerGateConfig:
    """Configuration for speaker identification gating."""

    threshold_value: float = 0.0
    threshold_type: Literal["absolute", "percentage"] = "absolute"
    mode: Literal["ignore", "warn", "enforce"] = "warn"
    exemplar_count: int = 2

    def __post_init__(self) -> None:
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
    """Configuration for workflow and batch processing."""

    # Analysis timeouts
    timeout_quick_seconds: int = 3600  # 1 hour for quick analysis
    timeout_full_seconds: int = 7200  # 2 hours for full analysis

    # Progress updates
    update_interval: float = 10.0  # seconds

    # Batch processing
    max_size_mb: int = 30  # File size filter threshold

    # Audio processing
    subprocess_timeout: int = 5  # seconds
    mp3_bitrate: str = "192k"
    conversion_time_factor: float = 0.5  # seconds per MB

    # Speaker identification gate
    speaker_gate: SpeakerGateConfig = field(default_factory=SpeakerGateConfig)

    # CLI post-processing menu: show pruning options (off by default)
    cli_pruning_enabled: bool = False

    # Default path when saving config from the CLI (empty = use project config path)
    default_config_save_path: str = ""


@dataclass
class TranscriptionConfig:
    """Configuration for transcription settings."""

    model_name: str = "large-v2"
    compute_type: str = "float16"
    # Default to English. This avoids WhisperX auto-detection picking the wrong
    # language (e.g., "cy") and makes language changes an explicit global choice
    # via config/env only.
    language: str = "en"
    batch_size: int = 16
    diarize: bool = True
    min_speakers: int = 1
    max_speakers: Optional[int] = 20  # None = no limit
    model_download_policy: Literal["anonymous", "require_token"] = "require_token"
    huggingface_token: str = ""

    def __post_init__(self) -> None:
        # Back-compat: older configs may store null or "auto".
        if self.language is None or str(self.language).strip().lower() in {
            "",
            "auto",
            "none",
        }:
            self.language = "en"


@dataclass
class InputConfig:
    """Configuration for input settings."""

    wav_folders: list[str] = field(
        default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"]
    )
    recordings_folders: list[str] = field(default_factory=lambda: [RECORDINGS_DIR])
    prefill_rename_with_date_prefix: bool = True
    # How to choose file selection UI: "prompt" = ask each time; "explore" = file browser; "direct" = type path
    file_selection_mode: Literal["prompt", "explore", "direct"] = "prompt"
    # Playback skip amounts (seconds) in file selection TUI: short (,/.) and long ([/])
    playback_skip_seconds_short: float = 10.0
    playback_skip_seconds_long: float = 60.0


@dataclass
class OutputConfig:
    """Configuration for output settings."""

    base_output_dir: str = OUTPUTS_DIR  # Default output directory
    create_subdirectories: bool = True
    overwrite_existing: bool = False
    dynamic_charts: Literal["auto", "on", "off"] = "auto"
    dynamic_views: Literal["auto", "on", "off"] = "auto"
    default_audio_folder: str = RECORDINGS_DIR
    default_transcript_folder: str = DIARISED_TRANSCRIPTS_DIR
    default_readable_transcript_folder: str = READABLE_TRANSCRIPTS_DIR
    audio_deduplication_threshold: float = (
        0.90  # Similarity threshold for audio duplicate detection (0.0 to 1.0)
    )


@dataclass
class GroupAnalysisConfig:
    """Configuration for group analysis (TranscriptSet)."""

    enabled: bool = True
    output_dir: str = GROUP_OUTPUTS_DIR
    persist_groups: bool = False
    enable_stats_aggregation: bool = True
    scaffold_by_session: bool = True
    scaffold_by_speaker: bool = True
    scaffold_comparisons: bool = True


@dataclass
class DashboardConfig:
    """Configuration for dashboard and UI settings."""

    schema_version: int = 2
    overview_charts: list[str] = field(default_factory=list)
    overview_missing_behavior: str = "skip"
    overview_max_items: int | None = None

    def __post_init__(self) -> None:
        if not self.overview_charts:
            try:
                from transcriptx.core.utils.chart_registry import (
                    get_default_overview_charts,
                )  # type: ignore[import-untyped]

                self.overview_charts = get_default_overview_charts()
            except Exception:
                self.overview_charts = []


def migrate_dashboard_config(data: dict) -> tuple[dict, bool]:
    """Migrate legacy dashboard config to the current schema."""
    if not isinstance(data, dict):
        return data, False

    schema_version = data.get("schema_version", 1)
    if schema_version >= 2:
        return data, False

    legacy_types = data.get("overview_chart_types") or []
    mapping = {
        "multispeaker_sentiment": ["sentiment.multi_speaker_sentiment.global"],
        "emotion_radar_all": ["emotion.radar.global"],
        "interaction_network": ["interactions.network.global"],
        "dominance_analysis": ["interactions.dominance.global"],
        "interaction_matrices": ["interactions.heatmap.global"],
        "momentum": ["momentum.momentum.global"],
        "cross_speaker_interactions": ["interactions.timeline.global"],
        "temporal_dashboard": [
            "temporal_dynamics.temporal_dashboard.global",
            "temporal_dynamics.temporal_dashboard_speaking_rate.global",
        ],
        "understandability": ["understandability.readability_indices.global"],
        "wordcloud_all": ["wordcloud.wordcloud.global.basic"],
    }

    overview_charts: list[str] = []
    for key in legacy_types:
        overview_charts.extend(mapping.get(key, []))

    if not overview_charts:
        from transcriptx.core.utils.chart_registry import get_default_overview_charts

        overview_charts = get_default_overview_charts()

    migrated = dict(data)
    migrated.pop("overview_chart_types", None)
    migrated["schema_version"] = 2
    migrated["overview_charts"] = overview_charts
    migrated.setdefault("overview_missing_behavior", "skip")
    migrated.setdefault("overview_max_items", None)
    return migrated, True
