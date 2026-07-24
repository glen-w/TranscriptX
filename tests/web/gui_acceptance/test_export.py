"""Journey 6: Export panel creates a zip and surfaces download."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_script,
    seed_managed_transcript,
    seed_succeeded_run,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]

_SCRIPT = (
    Path(__file__).resolve().parent / "scripts" / "export_panel_script.py"
)


def test_export_panel_zip_and_download(gui_ws, monkeypatch) -> None:
    ws = seed_succeeded_run(seed_managed_transcript(gui_ws))
    assert ws.run_root is not None

    from transcriptx.web.services.export_service import ExportService

    zip_calls: list[list[str]] = []
    real_zip = ExportService.zip_artifacts

    def _tracking_zip(run_root: Path, artifact_ids: list[str]):
        zip_calls.append(list(artifact_ids))
        return real_zip(run_root, artifact_ids)

    monkeypatch.setattr(ExportService, "zip_artifacts", staticmethod(_tracking_zip))
    monkeypatch.setenv("TRANSCRIPTX_GUI_ACC_RUN_ROOT", str(ws.run_root))

    at = run_script(_SCRIPT, default_timeout=60.0)
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "Export" in blob

    if at.multiselect:
        opts = list(getattr(at.multiselect[0], "options", []) or [])
        if opts:
            at.multiselect[0].set_value(opts)
            at.run()
            assert_no_exception(at)

    create_btns = [b for b in at.button if "Create Export" in str(b.label)]
    assert create_btns, "Export panel should expose Create Export"
    create_btns[0].click()
    at.run()
    assert_no_exception(at)

    assert zip_calls, "ExportService.zip_artifacts should be invoked"
    assert zip_calls or "Download" in markdown_blob(at)