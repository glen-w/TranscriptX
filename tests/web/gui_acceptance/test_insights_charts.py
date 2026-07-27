"""Journey 3: Insights and Charts render for a seeded run."""

from __future__ import annotations

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_page,
    seed_managed_transcript,
    seed_succeeded_run,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def _run_session(ws) -> dict:
    return {
        "subject_type": "transcript",
        "subject_id": ws.slug,
        "run_id": ws.run_id,
    }


def test_insights_and_charts_pages_render(gui_ws, tmp_path) -> None:
    ws = seed_succeeded_run(seed_managed_transcript(gui_ws))
    assert ws.slug and ws.run_id and ws.run_root
    scripts = tmp_path / "apptest_scripts"

    at_insights = run_page(
        "transcriptx.web.page_modules.insights",
        "render_insights",
        session={
            **_run_session(ws),
            "page": "Insights",
            "insights_section": "summary",
        },
        script_dir=scripts,
        default_timeout=60.0,
    )
    assert_no_exception(at_insights)
    insights_blob = markdown_blob(at_insights)
    assert "Insights" in insights_blob
    assert "Select a subject" not in insights_blob

    at_analysis = run_page(
        "transcriptx.web.page_modules.insights",
        "render_insights",
        session={
            **_run_session(ws),
            "page": "Insights",
            "insights_section": "analysis",
        },
        script_dir=scripts,
        default_timeout=60.0,
    )
    assert_no_exception(at_analysis)
    analysis_blob = markdown_blob(at_analysis)
    # Executive Summary belongs on Summary, not Analysis.
    assert "Executive Summary" not in analysis_blob

    at_charts = run_page(
        "transcriptx.web.page_modules.charts",
        "render_charts",
        session={**_run_session(ws), "page": "Charts"},
        script_dir=scripts,
        default_timeout=60.0,
    )
    assert_no_exception(at_charts)
    charts_blob = markdown_blob(at_charts)
    assert "Charts" in charts_blob
    assert "Select a subject" not in charts_blob
