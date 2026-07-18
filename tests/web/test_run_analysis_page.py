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


@pytest.mark.unit
def test_run_analysis_page_renders_post_success_action_links() -> None:
    """After a successful run, show homepage-style next-step links under the flash."""
    import transcriptx.web.page_modules.run_analysis as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_render_post_analysis_actions" in source
    assert "render_recent_run_actions" in source
    assert "_KEY_LAST_SUCCESS" in source
    assert 'key_prefix="post_run"' in source


@pytest.mark.unit
def test_run_summary_from_last_success_builds_run(
    tmp_path: Path,
) -> None:
    from datetime import datetime

    import transcriptx.web.page_modules.run_analysis as mod

    run_dir = tmp_path / "slug-a" / "20260718_093828_67580744"
    run_dir.mkdir(parents=True)
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}")

    summary = mod._run_summary_from_last_success(
        {
            "run_dir": str(run_dir),
            "run_id": "20260718_093828_67580744",
            "transcript_path": str(transcript),
            "subject_type": "transcript",
            "modules": ["stats"],
        }
    )
    assert summary is not None
    assert summary.run_id == "20260718_093828_67580744"
    assert summary.run_dir == run_dir
    assert summary.selected_modules == ["stats"]
    assert isinstance(summary.created_at, datetime)


@pytest.mark.unit
def test_render_post_analysis_actions_uses_recent_run_strip(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod
    from tests.web.streamlit_doubles import DummyHomeStreamlit

    DummyHomeStreamlit.session_state = {
        mod._KEY_LAST_SUCCESS: {
            "run_dir": "/tmp/out/slug/run1",
            "run_id": "run1",
            "transcript_path": "/tmp/t.json",
            "subject_type": "transcript",
            "modules": ["stats"],
        }
    }
    calls: list = []

    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        mod,
        "_run_summary_from_last_success",
        lambda _payload: SimpleNamespace(
            run_dir=Path("/tmp/out/slug/run1"),
            run_id="run1",
            transcript_path=Path("/tmp/t.json"),
        ),
    )
    monkeypatch.setattr(
        mod,
        "render_recent_run_actions",
        lambda run, **kwargs: calls.append((run, kwargs)),
    )

    mod._render_post_analysis_actions()

    assert calls
    assert calls[0][1]["key_prefix"] == "post_run"
