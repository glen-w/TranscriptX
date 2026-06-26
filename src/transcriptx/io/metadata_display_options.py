"""Cached accessors for metadata and duration display configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.utils.config.workflow import DashboardConfig, MetadataConfig

DurationSummaryStyle = Literal["compact", "minutes_only"]


@dataclass(frozen=True)
class DurationDisplayOptions:
    hours_threshold_seconds: int
    style: DurationSummaryStyle


def get_metadata_config() -> MetadataConfig:
    from transcriptx.core.utils.config import get_config

    return get_config().metadata


def get_duration_display_options() -> DurationDisplayOptions:
    from transcriptx.core.utils.config import get_config

    dashboard: DashboardConfig = get_config().dashboard
    return DurationDisplayOptions(
        hours_threshold_seconds=int(dashboard.duration_hours_threshold_seconds),
        style=dashboard.duration_summary_style,  # type: ignore[arg-type]
    )
