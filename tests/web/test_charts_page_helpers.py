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
    CHARTS_KEY_MODULE_SORT,
    CHARTS_KEY_OPEN_MODULES,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_SORT_ALPHA,
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
        CHARTS_KEY_MODULE_SORT: CHARTS_SORT_ALPHA,
        CHARTS_KEY_OPEN_MODULES: ["acts"],
        CHARTS_KEY_EXPORT_RESULT: SimpleNamespace(),
        CHARTS_KEY_EXPORT_SIG: frozenset({"x"}),
    }

    class _St:
        session_state = ss

    monkeypatch.setattr(mod, "st", _St)
    mod._ensure_charts_filters_for_run("slug", "run-2")
    assert ss[CHARTS_KEY_FILTERS_INIT] == "slug|run-2"
    assert ss[CHARTS_KEY_FILTER_MODULE] is None  # default
    assert ss[CHARTS_KEY_SOURCE_PRESET] == "All"
    assert ss[CHARTS_KEY_MODULE_SORT] == CHARTS_SORT_ALPHA  # preserved
    assert ss[CHARTS_KEY_OPEN_MODULES] == []
    assert CHARTS_KEY_EXPORT_RESULT not in ss
    assert CHARTS_KEY_EXPORT_SIG not in ss

    # Same identity: no reset
    ss[CHARTS_KEY_FILTER_MODULE] = "keep"
    mod._ensure_charts_filters_for_run("slug", "run-2")
    assert ss[CHARTS_KEY_FILTER_MODULE] == "keep"


@pytest.mark.unit
def test_source_return_to_all_does_not_keep_locked_preset(monkeypatch) -> None:
    import transcriptx.web.page_modules.charts as mod
    from transcriptx.web.state import CHARTS_KEY_FILTER_TAGS, CHARTS_KEY_TAGS_MULTI

    ss = {
        CHARTS_KEY_TAGS_MULTI: ["foo"],
        CHARTS_KEY_FILTER_TAGS: ["foo"],
    }

    class _St:
        session_state = ss

    monkeypatch.setattr(mod, "st", _St)
    mod._apply_source_tag_coupling("Group aggregate")
    assert ss[CHARTS_KEY_FILTER_TAGS] == ["group_aggregate"]
    assert ss[CHARTS_KEY_TAGS_MULTI] == []
    mod._apply_source_tag_coupling("All")
    assert ss[CHARTS_KEY_FILTER_TAGS] == []
    assert ss[CHARTS_KEY_TAGS_MULTI] == []


@pytest.mark.unit
def test_sort_is_dirty_and_reset_restores_module_family() -> None:
    from transcriptx.web.charts_filter_state import (
        charts_filters_are_dirty,
        reset_charts_filters_to_defaults,
    )
    from transcriptx.web.state import (
        CHARTS_FILTER_DEFAULTS,
        CHARTS_KEY_MODULE_SORT,
        CHARTS_SORT_ALPHA,
        CHARTS_SORT_MODULE_FAMILY,
    )

    session: dict = {
        key: (list(val) if isinstance(val, list) else val)
        for key, val in CHARTS_FILTER_DEFAULTS.items()
    }
    assert charts_filters_are_dirty(session) is False
    session[CHARTS_KEY_MODULE_SORT] = CHARTS_SORT_ALPHA
    assert charts_filters_are_dirty(session) is True
    reset_charts_filters_to_defaults(session)
    assert session[CHARTS_KEY_MODULE_SORT] == CHARTS_SORT_MODULE_FAMILY
    assert charts_filters_are_dirty(session) is False


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


@pytest.mark.unit
def test_render_charts_body_empty_shows_empty_state(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.charts as mod

    empty_calls: list = []
    shell_calls: list = []
    ctx = SimpleNamespace(
        subject=SimpleNamespace(subject_id="slug-a"),
        run_id="run-1",
        run_root=tmp_path,
    )

    monkeypatch.setattr(mod, "_ensure_charts_filters_for_run", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod.ArtifactService, "list_artifacts", staticmethod(lambda _root: [])
    )
    monkeypatch.setattr(mod, "compute_chart_badges", lambda _charts: ["0 charts"])
    monkeypatch.setattr(
        mod,
        "render_page_shell",
        lambda *a, **k: shell_calls.append((a, k)),
    )
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *a, **k: empty_calls.append((a, k)),
    )

    mod._render_charts_body(ctx)

    assert shell_calls
    assert shell_calls[0][0][0] == "Charts Gallery"
    assert shell_calls[0][0][1] is None  # no permanent browse description
    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No chart artifacts" in empty_calls[0][0][1]
