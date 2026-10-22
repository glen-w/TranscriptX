"""T0/T1 speaker-honesty banners and import captions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.speaker_honesty import (
    T0_NO_NAMED_SPEAKERS_BANNER,
    T1_IMPORT_PLACEHOLDER_CAPTION,
    render_t0_named_speaker_banner,
    render_t1_import_caption,
    should_show_t0_named_speaker_banner,
    should_show_t1_import_caption,
)


class _CaptureSt:
    def __init__(self) -> None:
        self.info_calls: list[str] = []
        self.caption_calls: list[str] = []

    def info(self, message: str) -> None:
        self.info_calls.append(message)

    def caption(self, message: str) -> None:
        self.caption_calls.append(message)


@pytest.mark.unit
def test_t0_banner_shows_only_when_named_count_is_zero() -> None:
    assert should_show_t0_named_speaker_banner(0) is True
    assert should_show_t0_named_speaker_banner(1) is False
    assert should_show_t0_named_speaker_banner(None) is False

    shown = _CaptureSt()
    assert render_t0_named_speaker_banner(shown, 0) is True
    assert shown.info_calls == [T0_NO_NAMED_SPEAKERS_BANNER]

    hidden = _CaptureSt()
    assert render_t0_named_speaker_banner(hidden, 2) is False
    assert hidden.info_calls == []


@pytest.mark.unit
def test_t1_import_caption_when_no_named_speakers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.speaker_extraction.named_speaker_count_for_path",
        lambda _path: 0,
    )
    path = tmp_path / "placeholder.json"
    assert should_show_t1_import_caption(path) is True
    st = _CaptureSt()
    assert render_t1_import_caption(st, path) is True
    assert st.caption_calls == [T1_IMPORT_PLACEHOLDER_CAPTION]


@pytest.mark.unit
def test_t1_import_caption_hidden_when_named(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.speaker_extraction.named_speaker_count_for_path",
        lambda _path: 2,
    )
    st = _CaptureSt()
    assert render_t1_import_caption(st, tmp_path / "named.json") is False
    assert st.caption_calls == []


@pytest.mark.unit
def test_overview_body_renders_t0_banner(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.page_modules.overview as mod
    from tests.web.streamlit_doubles import DummyHomeStreamlit
    from transcriptx.web.components.run_scoped_page import RunScopedPageContext

    info_calls: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def info(message: str, **_kwargs) -> None:
            info_calls.append(message)

    loader = SimpleNamespace()
    session_ctx = SimpleNamespace(services=SimpleNamespace(content_loader=loader))
    layout = SimpleNamespace(pages={"overview": SimpleNamespace(blocks=[])})

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "build_artifact_index",
        lambda *_a, **_k: SimpleNamespace(entries=[SimpleNamespace()]),
    )
    monkeypatch.setattr(mod, "build_context_from_session", lambda _ss: session_ctx)
    monkeypatch.setattr(mod, "load_active_layout", lambda _ss: layout)
    monkeypatch.setattr(mod, "_overview_blocks_fragment", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "named_speaker_count_from_content_loader", lambda _l: 0)

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(
            subject_type="transcript", subject_id="s1", scope="transcript"
        ),
        run_id="20260101_120000",
        run_root=tmp_path,
    )
    mod._render_overview_body(ctx)
    assert info_calls == [T0_NO_NAMED_SPEAKERS_BANNER]


@pytest.mark.unit
def test_t1_import_caption_hidden_on_extraction_error(
    monkeypatch, tmp_path: Path
) -> None:
    def _boom(_path):
        raise OSError("unreadable")

    monkeypatch.setattr(
        "transcriptx.core.utils.speaker_extraction.named_speaker_count_for_path",
        _boom,
    )
    assert should_show_t1_import_caption(tmp_path / "broken.json") is False


def _chart_artifact() -> Artifact:
    from transcriptx.web.models.artifact import Artifact

    return Artifact(
        id="c1",
        kind="chart_static",
        module="stats",
        scope="session",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="c1.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=[],
        title="c1",
    )


@pytest.mark.unit
def test_charts_page_renders_t0_banner(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.page_modules.charts as charts_mod
    from tests.web.streamlit_doubles import DummyHomeStreamlit

    info_calls: list[str] = []

    class _St(DummyHomeStreamlit):
        session_state: dict = {}

        @staticmethod
        def info(message: str, **_kwargs) -> None:
            info_calls.append(message)

        @staticmethod
        def text_input(*_a, **_k):
            return ""

        @staticmethod
        def columns(spec, **_k):
            from tests.web.streamlit_doubles import DummyColumn

            n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
            return tuple(DummyColumn() for _ in range(n))

        @staticmethod
        def segmented_control(*_a, **_k):
            return "All"

        @staticmethod
        def pills(*_a, **_k):
            return []

        @staticmethod
        def popover(*_a, **_k):
            from tests.web.streamlit_doubles import DummyForm

            return DummyForm()

        @staticmethod
        def multiselect(*_a, **_k):
            return []

        @staticmethod
        def checkbox(*_a, **_k):
            return False

    monkeypatch.setattr(charts_mod, "st", _St)
    monkeypatch.setattr(charts_mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(charts_mod, "_sync_derived_filter_keys", lambda: None)
    monkeypatch.setattr(
        charts_mod,
        "_build_view_from_session",
        lambda *_a, **_k: SimpleNamespace(
            module_groups=[],
            filtered_charts=[],
            overview_slots=[],
            matching_count=0,
        ),
    )
    monkeypatch.setattr(
        charts_mod, "named_speaker_count_from_content_loader", lambda *_a, **_k: 0
    )
    monkeypatch.setattr(
        charts_mod, "intersect_charts_open_modules", lambda *_a, **_k: []
    )
    monkeypatch.setattr(
        charts_mod, "ensure_charts_chart_text", lambda *_a, **_k: "none"
    )
    monkeypatch.setattr(
        charts_mod, "chart_text_flags", lambda *_a, **_k: (False, False)
    )
    monkeypatch.setattr(charts_mod, "compute_chart_badges", lambda *_a, **_k: [])
    monkeypatch.setattr(
        charts_mod, "_render_export_under_badges", lambda *_a, **_k: None
    )
    monkeypatch.setattr(charts_mod, "_render_filter_toolbar", lambda *_a, **_k: None)
    monkeypatch.setattr(charts_mod, "_render_section_nav", lambda **_k: "all")
    monkeypatch.setattr(charts_mod, "_render_module_row", lambda *_a, **_k: None)

    fragment = charts_mod._charts_filters_and_gallery_fragment
    inner = getattr(fragment, "__wrapped__", fragment)
    inner(
        tmp_path,
        [_chart_artifact()],
        [],
        [],
        [],
        [],
        [],
        None,
        "skip",
        False,
    )
    assert info_calls == [T0_NO_NAMED_SPEAKERS_BANNER]


@pytest.mark.unit
def test_charts_overview_block_renders_t0_banner(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.blocks.implementations.charts as charts_block

    info_calls: list[str] = []
    monkeypatch.setattr(
        charts_block,
        "st",
        SimpleNamespace(
            info=lambda message, **_k: info_calls.append(message),
            caption=lambda *_a, **_k: None,
            session_state={},
        ),
    )
    monkeypatch.setattr(
        charts_block, "_chart_artifacts", lambda *_a, **_k: [_chart_artifact()]
    )
    monkeypatch.setattr(
        "transcriptx.web.services.chart_view_model_service.named_speaker_count_from_content_loader",
        lambda *_a, **_k: 0,
    )
    monkeypatch.setattr(
        "transcriptx.web.services.chart_view_model_service.build_charts_gallery_view",
        lambda *_a, **_k: SimpleNamespace(overview_slots=[]),
    )
    monkeypatch.setattr(
        "transcriptx.core.config.resolve_effective_config",
        lambda **_k: SimpleNamespace(effective_config=SimpleNamespace(dashboard=None)),
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.charts._render_chart_family_section",
        lambda *_a, **_k: None,
    )
    ctx = SimpleNamespace(
        run_root=tmp_path,
        services=SimpleNamespace(content_loader=SimpleNamespace()),
    )
    charts_block.render_chart_overview_slots(ctx, SimpleNamespace())
    assert info_calls == [T0_NO_NAMED_SPEAKERS_BANNER]
