"""Workflow configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from transcriptx.core.utils.paths import (
    RECORDINGS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    DIARISED_TRANSCRIPTS_DIR,
    OUTPUTS_DIR,
    GROUP_OUTPUTS_DIR,
)


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


@dataclass
class TranscriptionConfig:
    """Configuration for transcription settings."""

    model_name: str = "large-v2"
    compute_type: str = "float16"
    language: str | None = None  # None means auto-detect (displayed as "auto" in UI)
    batch_size: int = 16
    diarize: bool = True
    min_speakers: int = 1
    max_speakers: int = 10
    model_download_policy: Literal["anonymous", "require_token"] = "anonymous"
    huggingface_token: str = ""


@dataclass
class InputConfig:
    """Configuration for input settings."""

    wav_folders: list[str] = field(
        default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"]
    )
    recordings_folders: list[str] = field(default_factory=lambda: [RECORDINGS_DIR])
    prefill_rename_with_date_prefix: bool = True


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
                )

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
