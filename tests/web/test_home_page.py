"""Tests for home page."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


def _patch_home_common(monkeypatch, mod, st_double=DummyHomeStreamlit) -> None:
    import transcriptx.web.components.action_links as action_links
    import transcriptx.web.components.recent_run_row as recent_run_row

    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(mod, "_cached_sessions_and_stats", lambda: ([], {}))
    monkeypatch.setattr(mod, "st", st_double)
    monkeypatch.setattr(action_links, "st", st_double)
    monkeypatch.setattr(recent_run_row, "st", st_double)


def test_home_initial_render_loads_recent_runs_without_groups(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    _patch_home_common(monkeypatch, mod)
    slug_label_calls = {"count": 0}
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: slug_label_calls.__setitem__("count", slug_label_calls["count"] + 1)
        or {},
    )
    calls = {"recent_runs": 0}

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "run-1"
        run_dir = Path("/tmp/slug-1/run-1")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]
        status = "completed"
        duration_seconds = 12.0
        profile_name = "balanced"

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            calls["recent_runs"] += 1
            return [_Run()]
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    mod.render_home()

    assert calls["recent_runs"] == 1
    assert slug_label_calls["count"] == 1


def test_home_skips_slug_labels_when_no_recent_runs(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    _patch_home_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "render_empty_state", lambda *_args, **_kwargs: None)
    slug_label_calls = {"count": 0}
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: slug_label_calls.__setitem__("count", slug_label_calls["count"] + 1)
        or {},
    )

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return []
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    mod.render_home()

    assert slug_label_calls["count"] == 0


def test_home_renders_transcript_overview_with_sessions_and_expanders(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "run-1"
        run_dir = Path("/tmp/slug-1/run-1")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]
        status = "completed"
        duration_seconds = 12.0
        profile_name = "balanced"

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return [_Run()]
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)
    monkeypatch.setattr(
        mod,
        "_cached_sessions_and_stats",
        lambda: (
            [
                {
                    "name": "session-a",
                    "duration_seconds": 90,
                    "word_count": 100,
                    "segment_count": 10,
                    "speaker_count": 2,
                    "analysis_completion": 80,
                }
            ],
            {
                "total_transcripts": 1,
                "total_sessions": 1,
                "total_duration_seconds": 90,
                "total_word_count": 100,
                "total_speakers": 2,
                "average_completion": 80,
            },
        ),
    )

    metrics: list[tuple] = []
    frames: list[object] = []
    subheaders: list[str] = []
    expanders: list[str] = []

    class _StatsHomeStreamlit(DummyHomeStreamlit):
        @staticmethod
        def metric(*args, **kwargs):
            metrics.append((args, kwargs))

        @staticmethod
        def dataframe(df, **_kwargs):
            frames.append(df)

        @staticmethod
        def subheader(label, **_kwargs):
            subheaders.append(str(label))

        @staticmethod
        def expander(label, **_kwargs):
            expanders.append(str(label))
            return DummyHomeStreamlit.expander(label, **_kwargs)

    import transcriptx.web.components.action_links as action_links
    import transcriptx.web.components.recent_run_row as recent_run_row

    monkeypatch.setattr(mod, "st", _StatsHomeStreamlit)
    monkeypatch.setattr(action_links, "st", _StatsHomeStreamlit)
    monkeypatch.setattr(recent_run_row, "st", _StatsHomeStreamlit)
    mod.render_home()

    assert "Transcript overview" not in subheaders
    assert "Per-session statistics" not in subheaders
    assert "Recent Runs" not in subheaders
    assert expanders == ["sessions", "Recent runs"]
    metric_labels = [args[0] for args, _ in metrics if args]
    assert metric_labels == [
        "Transcripts",
        "Sessions",
        "Total duration",
        "Total words",
        "Speakers (max)",
        "Analysis completion",
    ]
    assert frames
    assert list(frames[0]["Session"]) == ["session-a"]


def test_home_export_zip_prepares_download(monkeypatch) -> None:
    import transcriptx.web.components.recent_run_row as recent_run_row
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}

    class _ExportHomeStreamlit(DummyHomeStreamlit):
        downloads: list[dict[str, object]] = []

        @staticmethod
        def button(*_args, key=None, **_kwargs):
            return isinstance(key, str) and "home_run_ex_" in key

        @classmethod
        def download_button(cls, *args, **kwargs):
            cls.downloads.append({"args": args, "kwargs": kwargs})
            return False

    _patch_home_common(monkeypatch, mod, st_double=_ExportHomeStreamlit)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "run-1"
        run_dir = Path("/tmp/slug-1/run-1")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]
        status = "completed"
        duration_seconds = None
        profile_name = ""

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return [_Run()]
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    prepare_calls: list[object] = []

    def _fake_prepare(run) -> None:
        prepare_calls.append(run.run_id)
        DummyHomeStreamlit.session_state["recent_run_export_zip_run-1"] = {
            "bytes": b"zip-bytes",
            "filename": "run-1_export.zip",
        }

    monkeypatch.setattr(recent_run_row, "prepare_recent_run_export", _fake_prepare)
    mod.render_home()

    assert prepare_calls == ["run-1"]
    assert _ExportHomeStreamlit.downloads
    assert (
        _ExportHomeStreamlit.downloads[0]["kwargs"]["file_name"] == "run-1_export.zip"
    )
    assert _ExportHomeStreamlit.downloads[0]["kwargs"]["mime"] == "application/zip"


def test_home_recent_run_open_updates_session_state(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {
        "subject_id_selector": "",
        "run_selector": "stale-run",
        "subject_type_selector": "Group",
    }

    markdown_blobs: list[str] = []

    class _OpenHomeStreamlit(DummyHomeStreamlit):
        @staticmethod
        def markdown(body, **_kwargs):
            markdown_blobs.append(str(body))

        @staticmethod
        def button(*_args, key=None, on_click=None, args=(), kwargs=None, **_kw):
            if isinstance(key, str) and "home_run_ov_" in key and on_click:
                on_click(*(args or ()), **(kwargs or {}))
            return False

    _patch_home_common(monkeypatch, mod, st_double=_OpenHomeStreamlit)
    monkeypatch.setattr(
        mod, "_slug_display_labels_from_index", lambda: {"slug-1": "Suzanne interview"}
    )

    class _Run:
        created_at = datetime(2026, 7, 13, 3, 29)
        run_id = "20260713_032900_abcdef12"
        run_dir = Path("/tmp/slug-1/20260713_032900_abcdef12")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview", "charts"]
        status = "completed"
        duration_seconds = 90.0
        profile_name = "balanced"

    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: [_Run()] if name == "cached_list_recent_runs" else [],
    )

    mod.render_home()

    ss = _OpenHomeStreamlit.session_state
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "20260713_032900_abcdef12"
    assert ss["page"] == "Overview"
    assert ss["subject_type_selector"] == "Transcript"
    assert "subject_id_selector" not in ss
    assert "run_selector" not in ss

    joined = "\n".join(markdown_blobs)
    assert "Suzanne interview" in joined
    assert "Run 13 Jul 2026" in joined
    assert (
        "20260713_032900_abcdef12"
        not in joined.split("tx-recent-run-title")[1].split("tx-run-id-info")[0]
    )
    assert "Full run identifier" in joined
    assert "Output root" not in joined


@pytest.mark.parametrize(
    ("button_key_fragment", "expected_page"),
    [
        ("home_run_ch_", "Charts"),
        ("home_run_dt_", "Artifacts"),
    ],
)
def test_home_recent_run_action_links_navigate_to_target_page(
    monkeypatch, button_key_fragment: str, expected_page: str
) -> None:
    """Charts/Artifacts must keep run context; stale sidebar widgets must not win."""
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {
        "subject_id_selector": "",
        "run_selector": "other-run",
    }

    class _NavHomeStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, key=None, on_click=None, args=(), kwargs=None, **_kw):
            if isinstance(key, str) and button_key_fragment in key and on_click:
                on_click(*(args or ()), **(kwargs or {}))
            return False

    _patch_home_common(monkeypatch, mod, st_double=_NavHomeStreamlit)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})

    class _Run:
        created_at = datetime(2026, 7, 13, 3, 29)
        run_id = "20260713_032900_abcdef12"
        run_dir = Path("/tmp/slug-1/20260713_032900_abcdef12")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]
        status = "completed"
        duration_seconds = None
        profile_name = ""

    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: [_Run()] if name == "cached_list_recent_runs" else [],
    )

    mod.render_home()

    ss = _NavHomeStreamlit.session_state
    assert ss["page"] == expected_page
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "20260713_032900_abcdef12"
    assert "subject_id_selector" not in ss
    assert "run_selector" not in ss


def test_apply_subject_context_clears_stale_sidebar_widgets() -> None:
    from transcriptx.web.state import apply_subject_context

    state = {
        "subject_id_selector": "",
        "run_selector": "old",
        "subject_type_selector": "Group",
    }
    apply_subject_context(
        state,
        subject_type="transcript",
        subject_id="slug-a",
        run_id="run-a",
    )
    assert state["subject_type"] == "transcript"
    assert state["subject_id"] == "slug-a"
    assert state["run_id"] == "run-a"
    assert state["subject_type_selector"] == "Transcript"
    assert "subject_id_selector" not in state
    assert "run_selector" not in state


def test_apply_subject_context_pops_type_selector_when_widget_locked() -> None:
    """Mid-script updates must not crash after sidebar instantiated the widget."""
    from transcriptx.web.state import apply_subject_context

    class _LockedState(dict):
        def __setitem__(self, key, value):  # noqa: ANN001
            if key == "subject_type_selector":
                err = type("StreamlitAPIException", (Exception,), {})(
                    "cannot be modified after the widget is instantiated"
                )
                raise err
            return super().__setitem__(key, value)

    state = _LockedState(
        {
            "subject_id_selector": "stale",
            "run_selector": "old",
            "subject_type_selector": "Group",
        }
    )
    apply_subject_context(
        state,
        subject_type="transcript",
        subject_id="slug-a",
        run_id="run-a",
    )
    assert state["subject_type"] == "transcript"
    assert state["subject_id"] == "slug-a"
    assert state["run_id"] == "run-a"
    assert "subject_type_selector" not in state
    assert "subject_id_selector" not in state
    assert "run_selector" not in state


def test_home_recent_runs_perf_boundary_no_expensive_calls(monkeypatch) -> None:
    import transcriptx.web.components.recent_run_row as recent_run_row
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    _patch_home_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "opaque-run"
        run_dir = Path("/tmp/slug-1/opaque-run")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = []
        status = None
        duration_seconds = None
        profile_name = None

    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: [_Run()] if name == "cached_list_recent_runs" else [],
    )

    def _boom(*_a, **_k):
        raise AssertionError("expensive path called during Recent Runs render")

    monkeypatch.setattr(recent_run_row.ArtifactService, "list_artifacts", _boom)
    monkeypatch.setattr(recent_run_row.ExportService, "zip_artifacts", _boom)
    monkeypatch.setattr(recent_run_row.FileService, "resolve_transcript_path", _boom)

    mod.render_home()


def test_streamlit_min_declares_segmented_control_floor() -> None:
    req = Path(__file__).resolve().parents[2] / "requirements.txt"
    text = req.read_text(encoding="utf-8")
    assert "streamlit>=1.55.0" in text
    assert hasattr(__import__("streamlit"), "segmented_control")
