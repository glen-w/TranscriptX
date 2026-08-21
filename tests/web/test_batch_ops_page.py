"""Tests for batch analysis panel embedded on Run Analysis."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError


def _patch_sync_batch_worker(monkeypatch, mod) -> None:
    """Wait for the background worker so unit tests can assert in one render."""
    start = mod._start_pending_batch_worker

    def _sync(pending):
        start(pending)
        holder = DummyHomeStreamlit.session_state.get(mod._BATCH_WORKER_HOLDER_KEY)
        if not isinstance(holder, dict):
            raise AssertionError("batch worker holder missing")
        for _ in range(200):
            if holder.get("done"):
                return
            time.sleep(0.01)
        raise AssertionError("batch worker did not finish")

    monkeypatch.setattr(mod, "_start_pending_batch_worker", _sync)


@pytest.mark.unit
def test_batch_panel_renders_processed_runs_with_action_links(monkeypatch) -> None:
    import transcriptx.web.action_menus.render as action_render
    import transcriptx.web.components.action_links as action_links
    import transcriptx.web.components.recent_run_row as recent_run_row
    import transcriptx.web.page_modules.batch_ops as mod
    from tests.web.streamlit_doubles import DummyColumn

    DummyHomeStreamlit.session_state = {}
    markdown_blobs: list[str] = []
    action_keys: list[str] = []

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def markdown(body, **_kwargs):
            markdown_blobs.append(str(body))

        @staticmethod
        def button(*_args, key=None, **_kwargs):
            if isinstance(key, str):
                action_keys.append(key)
            return False

        @staticmethod
        def success(*_args, **_kwargs):
            return None

        @staticmethod
        def columns(n, **_kwargs):
            return tuple(
                DummyColumn() for _ in range(n if isinstance(n, int) else len(n))
            )

        @staticmethod
        def multiselect(*_args, **_kwargs):
            return []

        @staticmethod
        def selectbox(*_args, **_kwargs):
            return "quick"

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(action_links, "st", _BatchStreamlit)
    monkeypatch.setattr(recent_run_row, "st", _BatchStreamlit)
    monkeypatch.setattr(action_render, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "_slug_display_labels_from_index", lambda: {"slug-a": "Alice"}
    )

    run = SimpleNamespace(
        created_at=datetime(2026, 7, 13, 3, 29),
        run_id="20260713_032900_abcdef12",
        run_dir=Path("/tmp/slug-a/20260713_032900_abcdef12"),
        transcript_path=Path("/tmp/alice.json"),
        selected_modules=["overview"],
        status="completed",
        duration_seconds=12.0,
        profile_name="balanced",
    )
    DummyHomeStreamlit.session_state[mod._BATCH_RESULT_KEY] = SimpleNamespace(
        success=True,
        transcript_count=1,
        errors=[],
        message="Processed 1 transcript(s), 1 succeeded",
        runs=[run],
    )

    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", lambda: SimpleNamespace())

    mod.render_batch_analysis_panel()

    joined = "\n".join(markdown_blobs)
    assert "Processed runs" in joined
    assert "Alice" in joined
    # Keys: tx_al_batch_run__home_recent_runs__<action>__<digest>
    assert any("batch_run__" in k and "__open__" in k for k in action_keys)
    assert any("batch_run__" in k and "__charts__" in k for k in action_keys)
    assert any("batch_run__" in k and "__artifacts__" in k for k in action_keys)


@pytest.mark.unit
def test_sanitize_batch_widget_state_drops_stale_values(monkeypatch) -> None:
    import transcriptx.web.page_modules.batch_ops as mod

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/keep.json", "/gone.json"],
    }
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)

    mod._sanitize_batch_widget_state(["/keep.json"])

    assert DummyHomeStreamlit.session_state["batch_transcripts"] == ["/keep.json"]


@pytest.mark.unit
def test_sanitize_batch_widget_state_clears_non_list_values(monkeypatch) -> None:
    import transcriptx.web.page_modules.batch_ops as mod

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": "/not-a-list.json",
    }
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)

    mod._sanitize_batch_widget_state(["/keep.json"])

    assert DummyHomeStreamlit.session_state["batch_transcripts"] == []


def _stub_batch_config_ui(monkeypatch, mod) -> None:
    """Shared helpers so panel tests focus on launch/execute paths."""
    from transcriptx.core.analysis.selection import (
        EffectiveModulePlan,
        ResolvedAnalysisPreset,
    )

    resolved = ResolvedAnalysisPreset(
        preset="quick",
        mode="quick",
        profile="balanced",
        module_ids=("stats",),
    )
    plan = EffectiveModulePlan(
        module_ids=("stats",),
        llm_count=0,
        heavy_count=0,
        custom_qa_execution=False,
    )
    monkeypatch.setattr(mod, "render_analysis_preset_selector", lambda **_k: resolved)
    monkeypatch.setattr(
        mod,
        "render_custom_qa_picker",
        lambda **_k: (None, None, False),
    )
    monkeypatch.setattr(mod, "apply_custom_qa_to_plan", lambda *_a, **_k: plan)
    monkeypatch.setattr(mod, "render_effective_module_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_compact_llm_setup",
        lambda **_k: (None, [], "n/a"),
    )


@pytest.mark.unit
def test_batch_panel_form_cleared_flush_skips_execute(monkeypatch) -> None:
    """First pending paint marks form_cleared and reruns without executing."""
    import transcriptx.web.components.progress_panel as progress_panel
    import transcriptx.web.page_modules.batch_ops as mod
    from transcriptx.app.models.requests import BatchAnalysisRequest
    from transcriptx.app.progress import make_initial_snapshot

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/tmp/alice.json"],
        progress_panel.SNAPSHOT_KEY: make_initial_snapshot(1),
        mod._PENDING_BATCH_KEY: {
            "request": BatchAnalysisRequest(
                transcript_paths=[Path("/tmp/alice.json")],
                analysis_mode="quick",
                selected_modules=["stats"],
            ),
            "execute": True,
            "form_cleared": False,
            "started": False,
        },
    }
    reruns: list[bool] = []
    executed: list[bool] = []

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def rerun():
            reruns.append(True)

    class _Ctrl:
        def run_batch_analysis(self, _request, progress=None):
            executed.append(True)
            return SimpleNamespace(
                success=True, message="ok", runs=[], errors=[], transcript_count=1
            )

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(progress_panel, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_panel, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", _Ctrl)

    mod.render_batch_analysis_panel()

    pending = DummyHomeStreamlit.session_state[mod._PENDING_BATCH_KEY]
    assert pending["form_cleared"] is True
    assert pending["started"] is False
    assert reruns == [True]
    assert executed == []


@pytest.mark.unit
def test_batch_panel_controller_exception_shows_error_and_clears_cache(
    monkeypatch,
) -> None:
    import transcriptx.web.components.progress_panel as progress_panel
    import transcriptx.web.page_modules.batch_ops as mod
    from transcriptx.app.models.requests import BatchAnalysisRequest
    from transcriptx.app.progress import make_initial_snapshot

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/tmp/alice.json"],
        progress_panel.SNAPSHOT_KEY: make_initial_snapshot(1),
        mod._PENDING_BATCH_KEY: {
            "request": BatchAnalysisRequest(
                transcript_paths=[Path("/tmp/alice.json")],
                analysis_mode="quick",
                selected_modules=["stats"],
            ),
            "execute": True,
            "form_cleared": True,
            "started": False,
        },
        mod._BATCH_RESULT_KEY: SimpleNamespace(success=True, runs=[], errors=[]),
    }
    errors: list[str] = []
    cache_cleared: list[bool] = []

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def error(msg, **_kwargs):
            errors.append(str(msg))

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

        @staticmethod
        def rerun():
            return None

    class _Ctrl:
        def run_batch_analysis(self, _request, progress=None):
            raise ValidationError("transcript_paths must not be empty")

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(progress_panel, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_panel, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", _Ctrl)
    monkeypatch.setattr(
        mod, "clear_run_listing_caches", lambda: cache_cleared.append(True)
    )
    _patch_sync_batch_worker(monkeypatch, mod)

    mod.render_batch_analysis_panel()

    assert any("transcript_paths must not be empty" in e for e in errors)
    assert mod._BATCH_RESULT_KEY not in DummyHomeStreamlit.session_state
    assert cache_cleared == [True]


@pytest.mark.unit
def test_batch_panel_workflow_error_clears_prior_result(monkeypatch) -> None:
    import transcriptx.web.components.progress_panel as progress_panel
    import transcriptx.web.page_modules.batch_ops as mod
    from transcriptx.app.models.requests import BatchAnalysisRequest
    from transcriptx.app.progress import make_initial_snapshot

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/tmp/alice.json"],
        progress_panel.SNAPSHOT_KEY: make_initial_snapshot(1),
        mod._PENDING_BATCH_KEY: {
            "request": BatchAnalysisRequest(
                transcript_paths=[Path("/tmp/alice.json")],
                analysis_mode="quick",
                selected_modules=["stats"],
            ),
            "execute": True,
            "form_cleared": True,
            "started": False,
        },
        mod._BATCH_RESULT_KEY: SimpleNamespace(
            success=True, message="old", runs=[], errors=[]
        ),
    }
    errors: list[str] = []

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def error(msg, **_kwargs):
            errors.append(str(msg))

        @staticmethod
        def rerun():
            return None

    class _Ctrl:
        def run_batch_analysis(self, _request, progress=None):
            raise WorkflowExecutionError("pipeline blew up")

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(progress_panel, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_panel, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", _Ctrl)
    monkeypatch.setattr(mod, "clear_run_listing_caches", lambda: None)
    _patch_sync_batch_worker(monkeypatch, mod)

    mod.render_batch_analysis_panel()

    assert any("pipeline blew up" in e for e in errors)
    assert mod._BATCH_RESULT_KEY not in DummyHomeStreamlit.session_state


@pytest.mark.unit
def test_batch_panel_success_replaces_prior_result(monkeypatch) -> None:
    import transcriptx.web.components.progress_panel as progress_panel
    import transcriptx.web.page_modules.batch_ops as mod
    from transcriptx.app.models.requests import BatchAnalysisRequest
    from transcriptx.app.progress import make_initial_snapshot

    old = SimpleNamespace(success=True, message="old", runs=[], errors=[])
    new = SimpleNamespace(
        success=True, message="new", runs=[], errors=[], transcript_count=1
    )
    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/tmp/alice.json"],
        progress_panel.SNAPSHOT_KEY: make_initial_snapshot(1),
        mod._PENDING_BATCH_KEY: {
            "request": BatchAnalysisRequest(
                transcript_paths=[Path("/tmp/alice.json")],
                analysis_mode="quick",
                selected_modules=["stats"],
            ),
            "execute": True,
            "form_cleared": True,
            "started": False,
        },
        mod._BATCH_RESULT_KEY: old,
    }

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def success(*_args, **_kwargs):
            return None

        @staticmethod
        def rerun():
            return None

    class _Ctrl:
        def run_batch_analysis(self, _request, progress=None):
            return new

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(progress_panel, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_panel, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", _Ctrl)
    monkeypatch.setattr(mod, "clear_run_listing_caches", lambda: None)
    monkeypatch.setattr(mod, "_render_batch_result", lambda _r: None)
    _patch_sync_batch_worker(monkeypatch, mod)

    mod.render_batch_analysis_panel()

    assert DummyHomeStreamlit.session_state[mod._BATCH_RESULT_KEY] is new


@pytest.mark.unit
def test_batch_panel_execute_binds_live_progress_not_spinner(monkeypatch) -> None:
    """Pending batch must paint progress_slot and pass a progress callback."""
    import transcriptx.web.components.progress_panel as progress_panel
    import transcriptx.web.page_modules.batch_ops as mod
    from transcriptx.app.models.requests import BatchAnalysisRequest
    from transcriptx.app.progress import make_initial_snapshot

    progress_args: list = []

    DummyHomeStreamlit.session_state = {
        "batch_transcripts": ["/tmp/alice.json"],
        progress_panel.SNAPSHOT_KEY: make_initial_snapshot(1),
        mod._PENDING_BATCH_KEY: {
            "request": BatchAnalysisRequest(
                transcript_paths=[Path("/tmp/alice.json")],
                analysis_mode="quick",
                selected_modules=["stats"],
            ),
            "execute": True,
            "form_cleared": True,
            "started": False,
        },
    }

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def spinner(*_args, **_kwargs):
            raise AssertionError("batch must not wrap the run in st.spinner")

        @staticmethod
        def rerun():
            return None

    class _Ctrl:
        def run_batch_analysis(self, request, progress=None):
            progress_args.append(progress)
            if progress is not None:
                progress.on_log("Analyzing alice.json", level="info")
                progress.on_event(
                    {
                        "event": "module_started",
                        "module_name": "stats",
                        "index": 1,
                        "total": 1,
                    }
                )
            return SimpleNamespace(
                success=True,
                message="ok",
                runs=[],
                errors=[],
                transcript_count=1,
            )

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(progress_panel, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_panel, "render_progress_panel", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_batch_ops_selection_fragment", lambda *_a, **_k: None)
    _stub_batch_config_ui(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcript_picker_options",
        lambda: [SimpleNamespace(path="/tmp/alice.json", label="alice")],
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", _Ctrl)
    monkeypatch.setattr(mod, "clear_run_listing_caches", lambda: None)
    monkeypatch.setattr(mod, "_render_batch_result", lambda _r: None)
    _patch_sync_batch_worker(monkeypatch, mod)

    mod.render_batch_analysis_panel()

    assert progress_args and progress_args[0] is not None
    snap = DummyHomeStreamlit.session_state[progress_panel.SNAPSHOT_KEY]
    assert snap["status"] == "completed"
    assert any("Analyzing alice.json" in line for line in snap.get("recent_logs", []))


@pytest.mark.unit
def test_batch_ops_execute_contract_uses_live_panel() -> None:
    import transcriptx.web.page_modules.batch_ops as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "StreamlitProgressCallback" in source
    assert 'pending.get("form_cleared")' in source
    assert 'key="batch_ops_cancel"' in source
    assert 'key="batch_ops_skip"' in source
    assert 'with st.spinner("Running batch analysis...")' not in source


@pytest.mark.unit
def test_batch_ops_module_has_no_run_analysis_import() -> None:
    import transcriptx.web.page_modules.batch_ops as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "run_analysis" not in source
    assert "render_batch_ops_page" not in source
    assert hasattr(mod, "render_batch_analysis_panel")


@pytest.mark.unit
def test_streamlit_progress_stage_start_clears_completed_status(monkeypatch) -> None:
    """Batch resumes must not leave the prior transcript's Completed banner."""
    from transcriptx.app.progress import make_initial_snapshot
    from transcriptx.web.components import progress_panel as panel_mod
    from transcriptx.web.components.progress_panel import (
        SNAPSHOT_KEY,
        StreamlitProgressCallback,
    )

    session = {SNAPSHOT_KEY: make_initial_snapshot(2)}
    session[SNAPSHOT_KEY]["status"] = "completed"
    session[SNAPSHOT_KEY]["phase"] = "completed"

    class _St:
        session_state = session

    monkeypatch.setattr(panel_mod, "st", _St)
    cb = StreamlitProgressCallback()
    cb.on_stage_start("batch_analysis")
    assert session[SNAPSHOT_KEY]["status"] == "running"
    assert session[SNAPSHOT_KEY]["phase"] == "batch_analysis"
