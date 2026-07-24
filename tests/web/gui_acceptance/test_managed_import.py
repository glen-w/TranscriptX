"""Journey 1: managed import persists into Library."""

from __future__ import annotations

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_page,
    seed_managed_transcript,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def test_managed_import_appears_in_library(gui_ws, tmp_path) -> None:
    ws = seed_managed_transcript(gui_ws)
    assert ws.slug is not None
    assert ws.transcript_path is not None
    assert ws.transcript_path.exists()

    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    discovered = discover_managed_transcript_paths()
    assert any(p.name == f"{ws.slug}.json" for p in discovered)

    scripts = tmp_path / "apptest_scripts"
    at_import = run_page(
        "transcriptx.web.page_modules.upload_transcript",
        "render_upload_transcript_page",
        script_dir=scripts,
    )
    assert_no_exception(at_import)
    blob = markdown_blob(at_import)
    assert "Import" in blob or "Upload" in blob or "transcript" in blob.lower()

    at_lib = run_page(
        "transcriptx.web.page_modules.library",
        "render_library",
        script_dir=scripts,
    )
    assert_no_exception(at_lib)
    lib_blob = markdown_blob(at_lib)
    assert "Library" in lib_blob
    assert "No transcripts found" not in lib_blob
    assert at_lib.selectbox, "Library should expose a transcript picker when seeded"
