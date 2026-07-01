"""Pydantic schema for dashboard overview settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _chart_choices() -> list[str]:
    try:
        from transcriptx.core.utils.chart_registry import get_chart_registry

        return sorted(get_chart_registry().keys())
    except Exception:
        return []


def _default_overview_charts() -> list[str]:
    try:
        from transcriptx.core.utils.chart_registry import get_default_overview_charts

        return get_default_overview_charts()
    except Exception:
        return []


class DashboardOverviewSettingsModel(BaseModel):
    """Canonical field definitions for dashboard overview chart selection."""

    schema_version: int = Field(
        default=2, ge=1, description="Dashboard config schema version."
    )
    overview_charts: list[str] = Field(
        default_factory=_default_overview_charts,
        description="Ordered list of chart registry IDs for the overview.",
        json_schema_extra={"choices": _chart_choices()},
    )
    overview_missing_behavior: Literal["skip", "show_placeholder"] = Field(
        default="skip",
        description="Behavior when overview charts are missing.",
    )
    overview_max_items: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of overview charts to display.",
    )

    @field_validator("overview_charts")
    @classmethod
    def _validate_overview_chart_ids(cls, value: list[str]) -> list[str]:
        try:
            from transcriptx.core.utils.chart_registry import get_chart_registry

            valid_ids = set(get_chart_registry().keys())
        except Exception:
            valid_ids = set()
        invalid = [str(viz_id) for viz_id in value if str(viz_id) not in valid_ids]
        if invalid:
            raise ValueError("Unknown chart IDs: " + ", ".join(invalid))
        return value
