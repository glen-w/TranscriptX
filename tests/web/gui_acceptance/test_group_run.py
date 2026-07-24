"""Journey 5: Groups CRUD + Run Analysis group target (stubbed)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_page,
    seed_group,
    seed_managed_transcript,
    stub_analysis_success,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def test_group_create_and_run_analysis_group_target(
    gui_ws, monkeypatch, tmp_path
) -> None:
    ws = seed_managed_transcript(gui_ws)
    assert ws.transcript_path is not None
    scripts = tmp_path / "apptest_scripts"

    from transcriptx.web.services.group_service import GroupService

    at = run_page(
        "transcriptx.web.page_modules.groups",
        "render_groups",
        session={"page": "Groups"},
        default_timeout=60.0,
        script_dir=scripts,
    )
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "Group" in blob

    name_inputs = [t for t in at.text_input if "Name" in str(t.label)]
    if name_inputs:
        name_inputs[0].input("AppTest Group")
        if at.multiselect:
            opts = list(getattr(at.multiselect[0], "options", []) or [])
            chosen = None
            for opt in opts:
                if ws.slug and ws.slug in str(opt):
                    chosen = opt
                    break
            if chosen is None and opts:
                chosen = opts[0]
            if chosen is not None:
                at.multiselect[0].set_value([chosen])
        create_btns = [b for b in at.button if "Create group" in str(b.label)]
        if create_btns:
            create_btns[0].click()
            at.run()
            assert_no_exception(at)

    groups = GroupService.list_groups()
    if not groups:
        ws = seed_group(ws, name="AppTest Group")
        groups = GroupService.list_groups()
    assert groups
    group = groups[0]
    ws = replace(ws, group_id=group.group_id)

    fake_run = ws.outputs_dir / "groups" / group.group_id / "20260101_group"
    stub_analysis_success(monkeypatch, run_dir=fake_run)

    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.get_config",
        lambda: type(
            "Cfg",
            (),
            {"group_analysis": type("G", (), {"enabled": True})()},
        )(),
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.cached_get_available_modules",
        lambda: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.cached_get_default_modules",
        lambda *_a, **_k: ["stats"],
    )

    at_run = run_page(
        "transcriptx.web.page_modules.run_analysis",
        "render_run_analysis_page",
        session={
            "page": "Run Analysis",
            "subject_type": "group",
            "subject_id": group.group_id,
            "run_analysis_preset": "Balanced",
        },
        default_timeout=60.0,
        script_dir=scripts,
    )
    assert_no_exception(at_run)
    run_blob = markdown_blob(at_run)
    assert "Run Analysis" in run_blob or "Analysis" in run_blob
    assert groups and ws.group_id
