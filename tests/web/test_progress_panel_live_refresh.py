"""Live progress-panel refresh during a blocking run."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.progress import make_initial_snapshot
from transcriptx.web.components import progress_panel as panel_mod
from transcriptx.web.components.progress_panel import (
    SNAPSHOT_KEY,
    StreamlitProgressCallback,
)


@pytest.mark.unit
def test_streamlit_progress_callback_refreshes_render_slot(monkeypatch) -> None:
    """Bound render_slot must be re-painted on structured events (not spinner-only)."""
    paints: list[dict] = []
    session: dict = {SNAPSHOT_KEY: make_initial_snapshot(3)}

    class _Slot:
        def container(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class _St:
        session_state = session

    monkeypatch.setattr(panel_mod, "st", _St)
    monkeypatch.setattr(
        panel_mod,
        "render_progress_panel",
        lambda snap, **_k: paints.append(dict(snap)),
    )

    cb = StreamlitProgressCallback(render_slot=_Slot())
    cb.on_event(
        {
            "event": "module_started",
            "module_name": "stats",
            "index": 1,
            "total": 3,
        }
    )
    cb.on_event(
        {
            "event": "module_completed",
            "module_name": "stats",
            "index": 1,
            "total": 3,
            "completed": 1,
            "skipped": 0,
            "failed": 0,
        }
    )

    assert len(paints) >= 2
    assert paints[-1]["completed"] == 1
    assert paints[-1]["current_module"] == "stats" or paints[0][
        "current_module"
    ] == "stats"
    assert session[SNAPSHOT_KEY]["completed"] == 1


@pytest.mark.unit
def test_streamlit_progress_callback_without_slot_still_mutates_snapshot(
    monkeypatch,
) -> None:
    session: dict = {SNAPSHOT_KEY: make_initial_snapshot(2)}

    class _St:
        session_state = session

    monkeypatch.setattr(panel_mod, "st", _St)
    cb = StreamlitProgressCallback()
    cb.on_stage_start("running_pipeline")
    cb.on_event(
        {
            "event": "module_completed",
            "module_name": "ner",
            "completed": 1,
            "skipped": 0,
            "failed": 0,
            "total": 2,
        }
    )
    assert session[SNAPSHOT_KEY]["completed"] == 1
    assert session[SNAPSHOT_KEY]["phase"] == "running_pipeline"


@pytest.mark.unit
def test_run_analysis_execute_uses_live_panel_not_spinner() -> None:
    """Contract: pending launch must bind a progress slot and avoid spinner overlay."""
    import transcriptx.web.page_modules.run_analysis as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_slot=progress_slot" in source
    assert "st.empty()" in source
    assert "progress.refresh_panel()" in source
    # Spinner must not wrap the blocking run (it hid the live bar/count).
    assert 'with st.spinner("Running analysis…")' not in source
