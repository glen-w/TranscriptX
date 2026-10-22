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
