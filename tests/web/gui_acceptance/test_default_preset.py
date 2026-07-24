"""Journey 2: Run Analysis defaults to Balanced and launches (stubbed)."""

from __future__ import annotations

import pytest

from transcriptx.app.models.requests import AnalysisRequest
from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_page,
    seed_managed_transcript,
    stub_analysis_success,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def test_default_preset_balanced_and_stubbed_launch(
    gui_ws, monkeypatch, tmp_path
) -> None:
    ws = seed_managed_transcript(gui_ws)
    assert ws.slug is not None
    assert ws.transcript_path is not None

    fake_run = ws.outputs_dir / ws.slug / "20260101_apptest"
    calls = stub_analysis_success(monkeypatch, run_dir=fake_run)

    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.cached_get_available_modules",
        lambda: ["stats", "summary"],
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.cached_get_default_modules",
        lambda *_a, **_k: ["stats"],
    )

    scripts = tmp_path / "apptest_scripts"
    session = {
        "page": "Run Analysis",
        "subject_type": "transcript",
        "subject_id": ws.slug,
        "run_analysis_preset": "Balanced",
        "run_analysis_transcript": 1,
    }
    at = run_page(
        "transcriptx.web.page_modules.run_analysis",
        "render_run_analysis_page",
        session=session,
        default_timeout=60.0,
        script_dir=scripts,
    )
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "Run Analysis" in blob or "Analysis" in blob
    assert at.session_state["run_analysis_preset"] == "Balanced"
    launch_buttons = [b for b in at.button if "Run analysis" in str(b.label)]
    assert launch_buttons, "Run analysis launch control should be present"

    # Drive the two-phase launch executor without re-serializing fragile widgets
    # (AppTest + format_func selectboxes can fail on click/rerun).
    request = AnalysisRequest(
        transcript_path=ws.transcript_path,
        mode="custom",
        modules=["stats"],
        analysis_preset="balanced",
    )
    pending = {
        "target_type": "Transcript",
        "modules": ["stats"],
        "request": request,
        "transcript_path": str(ws.transcript_path),
        "selected_group": None,
        "started": False,
        "footer_summary": "Balanced · stubbed",
    }
    at2 = run_page(
        "transcriptx.web.page_modules.run_analysis",
        "render_run_analysis_page",
        session={
            "page": "Run Analysis",
            "run_analysis_preset": "Balanced",
            "analysis_run_in_progress": True,
            "run_analysis_pending_launch": pending,
        },
        default_timeout=60.0,
        script_dir=scripts,
    )
    assert_no_exception(at2)
    assert calls, "stubbed AnalysisController.run_analysis should run"
    assert str(getattr(calls[-1][1], "analysis_preset", "")).lower() == "balanced"
