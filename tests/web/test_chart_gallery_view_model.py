"""Unit tests for charts gallery view-model helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_display_name import gallery_module_display_name
from transcriptx.web.services.chart_view_model_service import (
    apply_chart_filters,
    build_charts_gallery_view,
    chart_matches_search,
    sort_gallery_module_ids,
)
from transcriptx.web.state import CHARTS_SORT_ALPHA, CHARTS_SORT_MODULE_FAMILY


def _chart(
    artifact_id: str,
    *,
    module: str = "stats",
    kind: str = "chart_static",
    scope: str | None = "global",
    speaker: str | None = None,
    tags: list[str] | None = None,
    title: str | None = None,
) -> Artifact:
    return Artifact(
        id=artifact_id,
        kind=kind,
        module=module,
        scope=scope,
        speaker=speaker,
        subview=None,
        slice_id=None,
        rel_path=f"{artifact_id}.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=tags or [],
        title=title or artifact_id,
    )


def _patch_overview_slots(monkeypatch, factory):
    monkeypatch.setattr(
        "transcriptx.web.services.chart_view_model_service.build_overview_slots",
        factory,
    )


@pytest.mark.unit
def test_gallery_module_display_name_short_titles() -> None:
    assert gallery_module_display_name("affect_tension") == "Affect tension"
    assert gallery_module_display_name("unknown_mod") == "Unknown Mod"
    assert gallery_module_display_name(None) == "Other"


@pytest.mark.unit
def test_sort_gallery_module_ids_alpha_and_family() -> None:
    ids = ["zzz_unknown", "affect_tension", "acts", "aaa_unknown"]
    alpha = sort_gallery_module_ids(ids, sort_mode=CHARTS_SORT_ALPHA)
    assert alpha[0] == "aaa_unknown"
    assert alpha.index("affect_tension") < alpha.index("zzz_unknown")
    assert "acts" in alpha
    family = sort_gallery_module_ids(ids, sort_mode=CHARTS_SORT_MODULE_FAMILY)
    assert family.index("acts") < family.index("affect_tension")
    assert family[-2:] == ["aaa_unknown", "zzz_unknown"]


@pytest.mark.unit
def test_sort_duplicate_display_names_tie_break_on_id() -> None:
    ids = ["beta_mod", "alpha_mod"]
    ordered = sort_gallery_module_ids(ids, sort_mode=CHARTS_SORT_ALPHA)
    assert ordered == ["alpha_mod", "beta_mod"]


@pytest.mark.unit
def test_search_matches_module_title_scope_speaker_tags() -> None:
    chart = _chart(
        "c1",
        module="affect_tension",
        title="Mismatch rate",
        scope="speaker",
        speaker="Alice",
        tags=["group_aggregate"],
    )
    assert chart_matches_search(chart, "affect")
    assert chart_matches_search(chart, "Mismatch")
    assert chart_matches_search(chart, "speaker")
    assert chart_matches_search(chart, "alice")
    assert chart_matches_search(chart, "group_aggregate")
    assert not chart_matches_search(chart, "nomatch")


@pytest.mark.unit
def test_apply_chart_filters_both_kinds_off_and_search() -> None:
    charts = [
        _chart("s", kind="chart_static", title="Static A"),
        _chart("d", kind="chart_dynamic", title="Dynamic B"),
    ]
    assert (
        apply_chart_filters(
            charts,
            module=None,
            scope=None,
            kind="__none__",
            tags=None,
            subview=None,
            slice_id=None,
        )
        == []
    )
    found = apply_chart_filters(
        charts,
        module=None,
        scope=None,
        kind=None,
        tags=None,
        subview=None,
        slice_id=None,
        search="Dynamic",
    )
    assert [c.id for c in found] == ["d"]


@pytest.mark.unit
def test_search_combined_with_module_and_kind_filters() -> None:
    charts = [
        _chart("a1", module="acts", kind="chart_static", title="Acts pie"),
        _chart("a2", module="acts", kind="chart_dynamic", title="Acts timeline"),
        _chart("s1", module="stats", kind="chart_static", title="Acts related stats"),
    ]
    found = apply_chart_filters(
        charts,
        module="acts",
        scope=None,
        kind="chart_static",
        tags=None,
        subview=None,
        slice_id=None,
        search="Acts",
    )
    assert [c.id for c in found] == ["a1"]


@pytest.mark.unit
def test_build_charts_gallery_view_single_filtered_collection(monkeypatch) -> None:
    charts = [
        _chart("g", module="acts", tags=["group_aggregate"], title="Group pie"),
        _chart("m", module="acts", tags=["member_session"], title="Member pie"),
        _chart("x", module="stats", tags=["other"], title="Stats"),
    ]

    def _fake_slots(*, overview_candidates, **_kwargs):
        if not overview_candidates:
            return []
        return [
            {
                "label": "slot",
                "viz_id": "acts.demo",
                "artifacts": list(overview_candidates),
                "description": None,
                "missing": False,
            }
        ]

    _patch_overview_slots(monkeypatch, _fake_slots)
    view = build_charts_gallery_view(
        charts,
        module=None,
        scope=None,
        kind=None,
        tags=["group_aggregate"],
        subview=None,
        slice_id=None,
        search="",
        sort_mode=CHARTS_SORT_MODULE_FAMILY,
        user_overview=[],
        missing_behavior="skip",
        max_items=None,
    )
    assert [c.id for c in view.filtered_charts] == ["g"]
    assert view.matching_count == 1
    assert view.overview_slots and [
        a.id for a in view.overview_slots[0]["artifacts"]
    ] == ["g"]
    assert [g.module_id for g in view.module_groups] == ["acts"]

    empty = build_charts_gallery_view(
        charts,
        module="stats",
        scope=None,
        kind=None,
        tags=["group_aggregate"],
        subview=None,
        slice_id=None,
        search="nomatch",
        sort_mode=CHARTS_SORT_ALPHA,
        user_overview=[],
        missing_behavior="skip",
        max_items=None,
    )
    assert empty.filtered_charts == []
    assert empty.overview_slots == []
    assert empty.module_groups == []


@pytest.mark.unit
def test_export_ids_match_filtered_gallery_collection(monkeypatch) -> None:
    from transcriptx.web.page_modules.charts import _charts_export_signature

    charts = [
        _chart("g", module="acts", tags=["group_aggregate"], title="Keep"),
        _chart("drop", module="acts", tags=["member_session"], title="Drop"),
    ]

    def _fake_slots(*, overview_candidates, **_kwargs):
        return [
            {
                "label": "slot",
                "viz_id": "acts.demo",
                "artifacts": list(overview_candidates),
                "description": None,
                "missing": False,
            }
        ]

    _patch_overview_slots(monkeypatch, _fake_slots)
    view = build_charts_gallery_view(
        charts,
        module=None,
        scope=None,
        kind=None,
        tags=["group_aggregate"],
        subview=None,
        slice_id=None,
        search="",
        sort_mode=CHARTS_SORT_MODULE_FAMILY,
        user_overview=[],
        missing_behavior="skip",
        max_items=None,
    )
    gallery_ids = {c.id for c in view.filtered_charts}
    overview_ids = {
        a.id for slot in view.overview_slots for a in (slot.get("artifacts") or [])
    }
    assert gallery_ids == {"g"}
    assert overview_ids <= gallery_ids
    assert _charts_export_signature(view.filtered_charts) == frozenset(gallery_ids)
    assert [g.module_id for g in view.module_groups] == ["acts"]


@pytest.mark.unit
def test_overview_hides_when_filters_leave_no_slots(monkeypatch) -> None:
    charts = [_chart("only", module="stats", title="Stats only")]
    _patch_overview_slots(monkeypatch, lambda **_kwargs: [])
    view = build_charts_gallery_view(
        charts,
        module="stats",
        scope=None,
        kind=None,
        tags=None,
        subview=None,
        slice_id=None,
        search="",
        sort_mode=CHARTS_SORT_ALPHA,
        user_overview=["acts.demo"],
        missing_behavior="skip",
        max_items=None,
    )
    assert view.filtered_charts  # module-only results remain
    assert view.overview_slots == []
    assert [g.module_id for g in view.module_groups] == ["stats"]


@pytest.mark.unit
def test_module_row_counts_reflect_filtered_kinds(monkeypatch) -> None:
    charts = [
        _chart("s1", module="acts", kind="chart_static"),
        _chart("s2", module="acts", kind="chart_static"),
        _chart("d1", module="acts", kind="chart_dynamic"),
        _chart("other", module="stats", kind="chart_static"),
    ]
    _patch_overview_slots(monkeypatch, lambda **_kwargs: [])
    view = build_charts_gallery_view(
        charts,
        module="acts",
        scope=None,
        kind=None,
        tags=None,
        subview=None,
        slice_id=None,
        search="",
        sort_mode=CHARTS_SORT_MODULE_FAMILY,
        user_overview=[],
        missing_behavior="skip",
        max_items=None,
    )
    assert len(view.module_groups) == 1
    group = view.module_groups[0]
    assert group.module_id == "acts"
    assert group.total == 3
    assert group.static == 2
    assert group.dynamic == 1
