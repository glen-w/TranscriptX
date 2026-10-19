"""Registry-level chart catalogue expectations by speaker layout (Theme A / P2)."""

from __future__ import annotations

from transcriptx.core.utils.chart_registry import (
    DEFAULT_OVERVIEW_VIZ_IDS,
    _MODULES_REQUIRING_MULTIPLE_NAMED_SPEAKERS,
    chart_requires_multiple_named_speakers,
    filter_overview_viz_ids_for_named_speakers,
    get_chart_definition,
    iter_chart_definitions,
)


def _presence_class(viz_id: str) -> str:
    chart_def = get_chart_definition(viz_id)
    assert chart_def is not None, viz_id
    if viz_id.startswith("group."):
        return "group_only"
    if chart_def.module in _MODULES_REQUIRING_MULTIPLE_NAMED_SPEAKERS:
        return "multi_only"
    if chart_requires_multiple_named_speakers(chart_def):
        return "multi_only"
    return "always"


def test_every_registry_viz_id_has_presence_class() -> None:
    for chart_def in iter_chart_definitions():
        assert _presence_class(chart_def.viz_id) in {
            "always",
            "multi_only",
            "group_only",
        }


def test_default_overview_excludes_multi_only_on_monologue() -> None:
    filtered = filter_overview_viz_ids_for_named_speakers(
        DEFAULT_OVERVIEW_VIZ_IDS,
        named_speaker_count=1,
    )
    assert filtered
    for viz_id in filtered:
        chart_def = get_chart_definition(viz_id)
        assert chart_def is not None
        assert not chart_requires_multiple_named_speakers(chart_def)


def test_default_overview_keeps_multi_charts_for_dialogue() -> None:
    filtered = filter_overview_viz_ids_for_named_speakers(
        DEFAULT_OVERVIEW_VIZ_IDS,
        named_speaker_count=2,
    )
    assert "interactions.network.global" in filtered
