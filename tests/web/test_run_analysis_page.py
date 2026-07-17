"""Run Analysis page thin Streamlit orchestration contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_run_analysis_empty_transcripts_renders_empty_state(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {}
    empty_calls: list[tuple] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def radio(_label, options, index=0, **_kwargs):
            return options[index]

        @staticmethod
        def selectbox(*_a, **_k):
            return 0

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

        @staticmethod
        def expander(*_a, **_k):
            return DummyHomeStreamlit.expander()

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: [])
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(mod, "cached_get_default_modules", lambda *_a, **_k: ["stats"])
    fragment_calls: list = []
    monkeypatch.setattr(
        mod,
        "_run_analysis_config_and_launch_fragment",
        lambda *args, **kwargs: fragment_calls.append(args),
    )

    mod.render_run_analysis_page()

    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No transcripts" in empty_calls[0][0][1]
    # Fragment still invoked with no transcript selected
    assert fragment_calls
    assert fragment_calls[0][1] is None


@pytest.mark.unit
def test_run_analysis_in_progress_skips_launch_fragment(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {
        "analysis_run_in_progress": True,
        mod.SNAPSHOT_KEY: {"status": "running", "pct": 10},
    }
    progress_calls: list = []
    fragment_calls: list = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def radio(_label, options, index=0, **_kwargs):
            return options[index]

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcripts",
        lambda: [SimpleNamespace(path=Path("/tmp/t.json"))],
    )
    monkeypatch.setattr(
        mod,
        "format_transcript_option_with_speaker_status",
        lambda t: str(t.path),
    )
    monkeypatch.setattr(
        mod.SubjectService, "index_in_path_options", lambda *_a, **_k: 0
    )
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(
        mod, "render_progress_panel", lambda snap: progress_calls.append(snap)
    )
    monkeypatch.setattr(
        mod,
        "_run_analysis_config_and_launch_fragment",
        lambda *args, **kwargs: fragment_calls.append(args),
    )

    # selectbox returns 0 = placeholder
    class _StSelect(_St):
        @staticmethod
        def selectbox(*_a, **_k):
            return 0

    monkeypatch.setattr(mod, "st", _StSelect)
    mod.render_run_analysis_page()

    assert progress_calls
    assert fragment_calls == []
