"""Charts page pure helpers and filter-init orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.export import ChartsExportResult
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.chart_view_model_service import (
    ChartGalleryFamily,
    ChartGallerySlice,
)
from transcriptx.web.state import (
    CHARTS_KEY_EXPORT_RESULT,
    CHARTS_KEY_EXPORT_SIG,
    CHARTS_KEY_FILTERS_INIT,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_SOURCE_PRESET,
)


def _chart(artifact_id: str, *, tags: list[str] | None = None) -> Artifact:
    return Artifact(
        id=artifact_id,
        kind="chart_static",
        module="stats",
        scope="session",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=f"{artifact_id}.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=tags or [],
        title=artifact_id,
    )


@pytest.mark.unit
def test_overview_candidate_charts_source_and_tags() -> None:
    from transcriptx.web.page_modules.charts import _overview_candidate_charts

    charts = [
        _chart("g", tags=["group_aggregate"]),
        _chart("m", tags=["member_session"]),
        _chart("both", tags=["group_aggregate", "member_session"]),
        _chart("plain", tags=["other"]),
        _chart("tagged", tags=["foo", "bar"]),
    ]
    assert [
        c.id for c in _overview_candidate_charts(charts, "Group aggregate", [])
    ] == [
        "g",
        "both",
    ]
    assert [
        c.id for c in _overview_candidate_charts(charts, "Member sessions", [])
    ] == ["m", "both"]
    assert [
        c.id for c in _overview_candidate_charts(charts, "All", ["foo", "bar"])
    ] == ["tagged"]
    assert len(_overview_candidate_charts(charts, "All", [])) == 5


@pytest.mark.unit
def test_family_renders_directly_cardinalities() -> None:
    from transcriptx.web.page_modules.charts import _family_renders_directly

    single = ChartGalleryFamily(
        key="s",
        label="S",
        description=None,
        cardinality="single",
        rank=0,
        slices=[ChartGallerySlice(key="all", label="", artifacts=[])],
    )
    paired = ChartGalleryFamily(
        key="p",
        label="P",
        description=None,
        cardinality="paired_static_dynamic",
        rank=1,
        slices=[ChartGallerySlice(key="all", label="", artifacts=[])],
    )
    multi = ChartGalleryFamily(
        key="m",
        label="M",
        description=None,
        cardinality="multi",
        rank=2,
        slices=[
            ChartGallerySlice(key="a", label="A", artifacts=[]),
            ChartGallerySlice(key="b", label="B", artifacts=[]),
        ],
    )
    multi_all = ChartGalleryFamily(
        key="ma",
        label="MA",
        description=None,
        cardinality="multi",
        rank=3,
        slices=[ChartGallerySlice(key="all", label="", artifacts=[])],
    )
    assert _family_renders_directly(single) is True
    assert _family_renders_directly(paired) is True
    assert _family_renders_directly(multi) is False
    assert _family_renders_directly(multi_all) is True


@pytest.mark.unit
def test_charts_export_signature_and_current_export() -> None:
    from transcriptx.web.page_modules.charts import (
        _charts_export_signature,
        _has_current_export,
    )

    charts = [_chart("a"), _chart("b")]
    sig = _charts_export_signature(charts)
    assert sig == frozenset({"a", "b"})
    result = ChartsExportResult(
        bytes=b"zip",
        filename="charts.zip",
        exported_count=2,
        omitted_count=0,
        module_count=1,
    )
    assert _has_current_export(result, sig, sig) is True
    assert _has_current_export(result, frozenset({"a"}), sig) is False
    assert _has_current_export("not-result", sig, sig) is False


@pytest.mark.unit
def test_ensure_charts_filters_for_run_resets_on_identity_change(monkeypatch) -> None:
    import transcriptx.web.page_modules.charts as mod

    ss = {
        CHARTS_KEY_FILTERS_INIT: "old|run",
        CHARTS_KEY_FILTER_MODULE: "noise",
        CHARTS_KEY_SOURCE_PRESET: "Member sessions",
        CHARTS_KEY_EXPORT_RESULT: SimpleNamespace(),
        CHARTS_KEY_EXPORT_SIG: frozenset({"x"}),
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)

    # st.session_state may be a special object; assign via module patch
    class _St:
        session_state = ss

    monkeypatch.setattr(mod, "st", _St)
    mod._ensure_charts_filters_for_run("slug", "run-2")
    assert ss[CHARTS_KEY_FILTERS_INIT] == "slug|run-2"
    assert ss[CHARTS_KEY_FILTER_MODULE] is None  # default
    assert ss[CHARTS_KEY_SOURCE_PRESET] == "All"
    assert CHARTS_KEY_EXPORT_RESULT not in ss
    assert CHARTS_KEY_EXPORT_SIG not in ss

    # Same identity: no reset
    ss[CHARTS_KEY_FILTER_MODULE] = "keep"
    mod._ensure_charts_filters_for_run("slug", "run-2")
    assert ss[CHARTS_KEY_FILTER_MODULE] == "keep"


@pytest.mark.unit
def test_render_charts_delegates_to_run_scoped_page(monkeypatch) -> None:
    import transcriptx.web.page_modules.charts as mod

    calls: list = []
    monkeypatch.setattr(
        mod,
        "render_run_scoped_page",
        lambda config, render_body, **kwargs: calls.append(
            (config, render_body, kwargs)
        )
        or True,
    )
    mod.render_charts()
    assert calls
    assert calls[0][0].title == "Charts Gallery"
    assert calls[0][1] is mod._render_charts_body
