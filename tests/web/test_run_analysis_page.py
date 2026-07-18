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
    radio_options: list[list[str]] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def radio(_label, options, index=0, **_kwargs):
            radio_options.append(list(options))
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

        @staticmethod
        def caption(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
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

    assert radio_options == [["Transcript", "Batch"]]
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

        @staticmethod
        def caption(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
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
    assert "render_batch_analysis_panel" in source
    assert "batch" in mod._RUN_ANALYSIS_DESCRIPTION.lower()
    # Post-actions must sit after the Batch early-return, not before Target.
    batch_branch = source.index('if target_type == "Batch":')
    batch_return = source.index("return", batch_branch)
    post_actions = source.index("_render_post_analysis_actions()", batch_return)
    assert post_actions > batch_return


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


def _run_analysis_st_base():
    class _St(DummyHomeStreamlit):
        radio_options_seen: list = []
        captions: list[str] = []
        target_choice: str | None = None

        @classmethod
        def radio(cls, _label, options, index=0, **_kwargs):
            cls.radio_options_seen.append(list(options))
            if cls.target_choice is not None and cls.target_choice in options:
                return cls.target_choice
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

        @classmethod
        def caption(cls, text, **_kwargs):
            cls.captions.append(str(text))

    return _St


@pytest.mark.unit
def test_run_analysis_transcript_path_invokes_post_actions(monkeypatch) -> None:
    """Single/group branch must call post-analysis actions; Batch must not."""
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {}
    post_calls: list[bool] = []
    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = "Transcript"

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod, "_render_post_analysis_actions", lambda: post_calls.append(True)
    )
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: [])
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(mod, "cached_get_default_modules", lambda *_a, **_k: ["stats"])
    monkeypatch.setattr(mod, "render_empty_state", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod, "_run_analysis_config_and_launch_fragment", lambda *_a, **_k: None
    )

    mod.render_run_analysis_page()

    assert post_calls == [True]
    assert _St.radio_options_seen[0] == ["Transcript", "Batch"]


@pytest.mark.unit
def test_run_analysis_group_target_hidden_when_disabled(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {}
    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: [])
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(mod, "cached_get_default_modules", lambda *_a, **_k: ["stats"])
    monkeypatch.setattr(mod, "render_empty_state", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod, "_run_analysis_config_and_launch_fragment", lambda *_a, **_k: None
    )

    mod.render_run_analysis_page()

    assert _St.radio_options_seen
    assert _St.radio_options_seen[0] == ["Transcript", "Batch"]
    assert any("Enable group analysis" in c for c in _St.captions)


@pytest.mark.unit
def test_run_analysis_group_enabled_empty_groups_empty_state(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {}
    empty_calls: list[tuple] = []
    fragment_calls: list = []
    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = "Group"

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(mod, "cached_list_groups", lambda: [])
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "_run_analysis_config_and_launch_fragment",
        lambda *args, **kwargs: fragment_calls.append(args),
    )

    mod.render_run_analysis_page()

    assert _St.radio_options_seen[0] == ["Transcript", "Group", "Batch"]
    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No groups yet" in empty_calls[0][0][1]
    assert fragment_calls
    assert fragment_calls[0][0] == "Group"
    assert fragment_calls[0][2] is None


@pytest.mark.unit
def test_run_analysis_batch_target_skips_single_run_paths(monkeypatch) -> None:
    """Batch must not call post-actions, module defaults, progress, or launch fragment."""
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {"run_analysis_target": "Batch"}
    panel_calls: list[bool] = []
    post_calls: list[bool] = []
    fragment_calls: list = []
    list_calls: list[bool] = []
    module_calls: list[bool] = []
    progress_calls: list = []

    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = "Batch"

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(
        mod,
        "render_batch_analysis_panel",
        lambda: panel_calls.append(True),
    )
    monkeypatch.setattr(
        mod,
        "_render_post_analysis_actions",
        lambda: post_calls.append(True),
    )
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcripts",
        lambda: list_calls.append(True) or [],
    )
    monkeypatch.setattr(
        mod,
        "cached_get_available_modules",
        lambda: module_calls.append(True) or ["stats"],
    )
    monkeypatch.setattr(
        mod,
        "cached_get_default_modules",
        lambda *_a, **_k: module_calls.append(True) or ["stats"],
    )
    monkeypatch.setattr(
        mod,
        "render_progress_panel",
        lambda snap: progress_calls.append(snap),
    )
    monkeypatch.setattr(
        mod,
        "_run_analysis_config_and_launch_fragment",
        lambda *args, **kwargs: fragment_calls.append(args),
    )

    mod.render_run_analysis_page()

    assert panel_calls == [True]
    assert post_calls == []
    assert list_calls == []
    assert module_calls == []
    assert progress_calls == []
    assert fragment_calls == []
    assert _St.radio_options_seen[0] == ["Transcript", "Group", "Batch"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("persisted", "group_enabled", "expected"),
    [
        ("Batch", False, "Batch"),
        ("Batch", True, "Batch"),
        ("Group", False, "Transcript"),
        ("Group", True, "Group"),
        ("nope", True, "Transcript"),
        (None, False, "Transcript"),
    ],
)
def test_normalize_run_analysis_target(
    monkeypatch, persisted, group_enabled, expected
) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    ss: dict = {}
    if persisted is not None:
        ss[mod._RUN_ANALYSIS_TARGET_KEY] = persisted
    DummyHomeStreamlit.session_state = ss
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)

    assert (
        mod._normalize_run_analysis_target(group_target_available=group_enabled)
        == expected
    )
    assert DummyHomeStreamlit.session_state[mod._RUN_ANALYSIS_TARGET_KEY] == expected


@pytest.mark.unit
def test_run_analysis_batch_with_group_disabled_still_offers_batch(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    DummyHomeStreamlit.session_state = {"run_analysis_target": "Batch"}
    panel_calls: list[bool] = []
    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = "Batch"

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(
        mod, "render_batch_analysis_panel", lambda: panel_calls.append(True)
    )
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
    monkeypatch.setattr(
        mod, "_run_analysis_config_and_launch_fragment", lambda *_a, **_k: None
    )

    mod.render_run_analysis_page()

    assert _St.radio_options_seen[0] == ["Transcript", "Batch"]
    assert panel_calls == [True]


@pytest.mark.unit
def test_run_analysis_group_enabled_selects_group(monkeypatch) -> None:
    import transcriptx.web.page_modules.run_analysis as mod
    from transcriptx.core.domain.group import Group

    DummyHomeStreamlit.session_state = {
        "subject_type": "group",
        "subject_id": "g-1",
    }
    fragment_calls: list = []
    group = Group(group_id="g-1", name="Alpha", members=["/tmp/a.json"])
    _St = _run_analysis_st_base()
    _St.radio_options_seen = []
    _St.captions = []
    _St.target_choice = "Group"

    class _StSelect(_St):
        @staticmethod
        def selectbox(_label, options, index=0, **_kwargs):
            # options are ["", ...group keys]; pick g-1
            if "g-1" in options:
                return "g-1"
            return options[index]

    monkeypatch.setattr(mod, "st", _StSelect)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_post_analysis_actions", lambda: None)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(group_analysis=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(mod, "cached_list_groups", lambda: [group])
    monkeypatch.setattr(
        mod.GroupService,
        "get_members",
        lambda _g: [SimpleNamespace(file_path="/tmp/a.json")],
    )
    real_exists = Path.exists

    def _exists(self: Path) -> bool:
        if str(self) == "/tmp/a.json":
            return True
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr(mod, "cached_get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(
        mod, "cached_get_default_modules_for_paths", lambda *_a, **_k: ["stats"]
    )
    monkeypatch.setattr(
        mod,
        "cached_get_module_info_list",
        lambda: [{"name": "stats", "supports_group": True}],
    )
    monkeypatch.setattr(
        mod,
        "_run_analysis_config_and_launch_fragment",
        lambda *args, **kwargs: fragment_calls.append(args),
    )

    mod.render_run_analysis_page()

    assert fragment_calls
    assert fragment_calls[0][0] == "Group"
    assert fragment_calls[0][2] is group
