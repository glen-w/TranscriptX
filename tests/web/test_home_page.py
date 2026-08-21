"""Tests for home page."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit
from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    CorrectionsState,
    CorrectionsStatus,
    FieldIntegrity,
    FileStamp,
    InventoryFingerprint,
    InventoryRow,
    SpeakerIdState,
    SpeakerIdStatus,
)


def _sample_rows() -> list[InventoryRow]:
    return [
        InventoryRow(
            transcript_path=Path("/tmp/slug-1.json"),
            transcript_key="k1",
            slug="slug-1",
            title="Interview Alice",
            imported_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            duration_seconds=4920,
            speaker_count=3,
            word_count=10430,
            source_id="whisperx",
            listing_integrity=FieldIntegrity.OK,
            speaker=SpeakerIdState(
                status=SpeakerIdStatus.NONE, integrity=FieldIntegrity.MISSING
            ),
            corrections=CorrectionsState(
                status=CorrectionsStatus.NEVER_STARTED,
                integrity=FieldIntegrity.MISSING,
            ),
            analysis=AnalysisState(
                status=AnalysisStatus.UNANALYSED, integrity=FieldIntegrity.MISSING
            ),
            last_activity_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
            fingerprint=InventoryFingerprint(stamps=(FileStamp("/tmp/slug-1.json", 1, 1),)),
        )
    ]


def _patch_home_common(monkeypatch, mod, st_double=DummyHomeStreamlit) -> None:
    import transcriptx.web.action_menus.handlers as am_handlers
    import transcriptx.web.action_menus.render as am_render
    import transcriptx.web.action_menus.services as am_services
    import transcriptx.web.components.action_links as action_links
    import transcriptx.web.components.recent_run_row as recent_run_row

    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(mod, "get_cached_corpus_inventory", _sample_rows)
    monkeypatch.setattr(mod, "st", st_double)
    monkeypatch.setattr(action_links, "st", st_double)
    monkeypatch.setattr(recent_run_row, "st", st_double)
    monkeypatch.setattr(am_render, "st", st_double)
    monkeypatch.setattr(am_handlers, "st", st_double)
    monkeypatch.setattr(am_services, "st", st_double)


def test_home_renders_launchpad_sections_in_order(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    subheaders: list[str] = []

    class _OrderHome(DummyHomeStreamlit):
        @staticmethod
        def subheader(title, **_kwargs):
            subheaders.append(str(title))

    _patch_home_common(monkeypatch, mod, st_double=_OrderHome)
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: (
            [] if name == "cached_list_recent_runs" else fn()
        ),
    )
    mod.render_home()

    assert subheaders == ["Recent activity", "Needs attention", "Continue working"]


def _make_recent_runs(count: int) -> list[object]:
    runs = []
    for index in range(count):
        run = type(
            f"_Run{index}",
            (),
            {
                "created_at": datetime(2026, 3, 25, 10, index),
                "run_id": f"run-{index}",
                "run_dir": Path(f"/tmp/slug-1/run-{index}"),
                "transcript_path": Path("/tmp/slug-1.json"),
                "selected_modules": ["overview"],
                "status": "completed",
                "duration_seconds": 12.0,
                "profile_name": "balanced",
            },
        )()
        runs.append(run)
    return runs


def test_home_recent_activity_shows_three_then_expands_to_ten(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    rendered: list[int] = []

    class _ExpandHome(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, key=None, **_kwargs):
            return key == "home_recent_activity_show_more"

    _patch_home_common(monkeypatch, mod, st_double=_ExpandHome)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})
    monkeypatch.setattr(
        mod,
        "render_recent_run_row",
        lambda run, row_index, slug_labels: rendered.append(row_index),
    )
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: (
            _make_recent_runs(10)
            if name == "cached_list_recent_runs"
            else _sample_rows()
            if name == "cached_corpus_inventory"
            else fn()
        ),
    )

    mod.render_home()
    assert rendered == [0, 1, 2]
    assert _ExpandHome.session_state.get(mod._HOME_RECENT_ACTIVITY_EXPANDED) is True

    rendered.clear()
    mod.render_home()
    assert rendered == list(range(10))


def test_home_empty_corpus_skips_recent_runs(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    _patch_home_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "get_cached_corpus_inventory", lambda: [])
    slug_label_calls = {"count": 0}
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: slug_label_calls.__setitem__("count", slug_label_calls["count"] + 1)
        or {},
    )
    calls = {"recent_runs": 0}

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            calls["recent_runs"] += 1
            return []
        return fn()

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)
    mod.render_home()

    assert calls["recent_runs"] == 0
    assert slug_label_calls["count"] == 0


def test_home_loads_recent_activity_on_launchpad(monkeypatch) -> None:
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
        if name == "cached_corpus_inventory":
            return _sample_rows()
        return fn()

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)
    mod.render_home()

    assert calls["recent_runs"] == 1
    assert slug_label_calls["count"] == 1


def test_home_skips_slug_labels_when_no_recent_runs(monkeypatch) -> None:
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

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return []
        if name == "cached_corpus_inventory":
            return _sample_rows()
        return fn()

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)
    mod.render_home()

    assert slug_label_calls["count"] == 0


def test_home_renders_corpus_summary_from_inventory(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    metrics: list[tuple] = []

    class _SummaryHome(DummyHomeStreamlit):
        @staticmethod
        def metric(*args, **kwargs):
            metrics.append((args, kwargs))

    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})
    monkeypatch.setattr(mod, "get_cached_corpus_inventory", _sample_rows)
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *args, **kwargs: (
            [] if name == "cached_list_recent_runs" else fn()
        ),
    )
    monkeypatch.setattr(mod, "st", _SummaryHome)
    mod.render_home()

    metric_labels = [args[0] for args, _ in metrics if args]
    assert metric_labels == ["Transcripts", "Analysed transcripts", "Total duration"]
    metric_values = {args[0]: args[1] for args, _ in metrics if len(args) >= 2}
    assert metric_values["Transcripts"] == 1
    assert metric_values["Analysed transcripts"] == 0


def test_home_needs_attention_navigates_with_library_filter(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod
    from transcriptx.app.corpus_inventory.models import LibraryWorkflowPreset
    from transcriptx.web.state import LIBRARY_NAV_FILTER, PAGE_KEY

    DummyHomeStreamlit.session_state = {}

    class _ClickHome(DummyHomeStreamlit):
        session_state: dict[str, object] = {}

        @staticmethod
        def button(label, key=None, **_kwargs):
            return key == "home_attention_needs_speaker_id"

    _patch_home_common(monkeypatch, mod, st_double=_ClickHome)
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda name, fn, *a, **k: (
            [] if name == "cached_list_recent_runs" else fn()
        ),
    )
    mod.render_home()
    assert _ClickHome.session_state.get(PAGE_KEY) == "Library"
    nav_filter = _ClickHome.session_state.get(LIBRARY_NAV_FILTER)
    assert nav_filter is not None
    assert nav_filter.preset is LibraryWorkflowPreset.NEEDS_SPEAKER_ID


def test_home_continue_pairs_run_id_with_run_dir(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    row = replace(
        _sample_rows()[0],
        analysis=AnalysisState(
            status=AnalysisStatus.COMPLETED,
            integrity=FieldIntegrity.OK,
            latest_run_id="run-1",
        ),
    )
    captured: dict[str, object] = {}

    def _nav(identity, page):
        captured["identity"] = identity
        captured["page"] = page

    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "navigate_with_identity", _nav)
    mod._open_continue_item(row)

    identity = captured["identity"]
    assert identity.run_id == "run-1"
    assert identity.run_dir is not None
    assert identity.run_dir.name == "run-1"


def test_home_export_zip_prepares_download(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}

    class _ExportHomeStreamlit(DummyHomeStreamlit):
        downloads: list[dict[str, object]] = []

        @staticmethod
        def button(*_args, key=None, **_kwargs):
            return isinstance(key, str) and "__export_zip__" in key

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
        if name == "cached_corpus_inventory":
            return _sample_rows()
        return fn()

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    prepare_calls: list[object] = []

    def _fake_prepare(identity) -> None:
        prepare_calls.append(identity.run_id)
        DummyHomeStreamlit.session_state[
            "action_menu_export_zip_transcript_slug-1_run-1"
        ] = {
            "bytes": b"zip-bytes",
            "filename": "run-1_export.zip",
        }

    import transcriptx.web.action_menus.handlers as am_handlers

    monkeypatch.setattr(am_handlers, "prepare_run_export", _fake_prepare)
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
            if isinstance(key, str) and "__open__" in key and on_click:
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
        lambda name, fn, *a, **k: (
            [_Run()]
            if name == "cached_list_recent_runs"
            else _sample_rows()
            if name == "cached_corpus_inventory"
            else []
        ),
    )

    mod.render_home()

    ss = _OpenHomeStreamlit.session_state
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "20260713_032900_abcdef12"
    assert ss["page"] == "Overview"
    assert ss["subject_type_selector"] == "Transcript"
    assert ss["subject_id_selector"] == "slug-1"
    assert ss["run_selector"] == "20260713_032900_abcdef12"

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
        ("__charts__", "Charts"),
        ("__artifacts__", "Artifacts"),
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
        lambda name, fn, *a, **k: (
            [_Run()]
            if name == "cached_list_recent_runs"
            else _sample_rows()
            if name == "cached_corpus_inventory"
            else []
        ),
    )

    mod.render_home()

    ss = _NavHomeStreamlit.session_state
    assert ss["page"] == expected_page
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == "slug-1"
    assert ss["run_id"] == "20260713_032900_abcdef12"
    assert ss["subject_id_selector"] == "slug-1"
    assert ss["run_selector"] == "20260713_032900_abcdef12"


def test_apply_subject_context_syncs_sidebar_widgets() -> None:
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
    assert state["subject_id_selector"] == "slug-a"
    assert state["run_selector"] == "run-a"


def test_apply_subject_context_pops_widgets_when_locked() -> None:
    """Mid-script updates must not crash after sidebar instantiated the widgets."""
    from transcriptx.web.state import apply_subject_context

    class _LockedState(dict):
        def __setitem__(self, key, value):  # noqa: ANN001
            if key in (
                "subject_type_selector",
                "subject_id_selector",
                "run_selector",
            ):
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
        lambda name, fn, *a, **k: (
            [_Run()]
            if name == "cached_list_recent_runs"
            else _sample_rows()
            if name == "cached_corpus_inventory"
            else []
        ),
    )

    import transcriptx.web.action_menus.services as am_services

    def _boom(*_a, **_k):
        raise AssertionError("expensive path called during Recent Runs render")

    monkeypatch.setattr(am_services.ArtifactService, "list_artifacts", _boom)
    monkeypatch.setattr(am_services.ExportService, "zip_artifacts", _boom)
    monkeypatch.setattr(am_services.FileService, "resolve_transcript_path", _boom)

    mod.render_home()


def test_cached_home_light_summary_skips_missing_paths(
    monkeypatch, tmp_path: Path
) -> None:
    import transcriptx.web.cache_helpers as mod

    present = tmp_path / "ok.json"
    present.write_text("{}", encoding="utf-8")
    missing = tmp_path / "gone.json"

    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.list_all_transcripts",
        lambda: [
            {"slug": "present", "source_path": str(present)},
            {"slug": "missing", "source_path": str(missing)},
            {"slug": "no-path"},
        ],
    )

    summary = mod.cached_home_light_summary.__wrapped__(
        ("slug-a/run1", "slug-a/run2", "slug-b/run1"),
        None,
    )
    assert summary["library_transcript_count"] == 2
    assert summary["analysed_transcript_count"] == 2
    assert summary["session_count"] == 3
    assert summary["has_any"] is True


def test_streamlit_min_declares_segmented_control_floor() -> None:
    req = Path(__file__).resolve().parents[2] / "requirements.txt"
    text = req.read_text(encoding="utf-8")
    assert "streamlit>=1.55.0" in text
    assert hasattr(__import__("streamlit"), "segmented_control")
