"""Speakers page facade re-exports UI slice renderers."""

from __future__ import annotations

import pytest

from transcriptx.web.page_modules import speakers as facade
from transcriptx.web.ui.speakers import charts, detail, directory, forms, support


@pytest.mark.unit
def test_speakers_facade_reexports_ui_slices() -> None:
    assert facade.render_speakers_page is directory.render_speakers_page
    assert facade._render_profile_detail is detail._render_profile_detail
    assert facade._render_detail_charts is charts._render_detail_charts
    assert facade._render_edit_form is forms._render_edit_form
    assert facade._service is support._service
    assert facade._methodology_lines is support._methodology_lines
