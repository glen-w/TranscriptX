"""Workflow 2: Identify and name speakers — name speakers and confirm on Transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    fill_assign_name,
    goto_app,
    nav,
    open_speaker_identification,
    page_text,
    select_transcript,
    speaker_workspace_text,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_DISPLAY_NAME = "Alex Facilitator"


def test_speaker_trust_name_and_confirm(seeded_run_app, page) -> None:
    """Name a diarized speaker and confirm the label on the Transcript viewer.

    Transcript VIEW requires transcript subject + run_id (see
    ``context_readiness``), so this journey uses a seeded completed run.
    """
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    # CCv2 sample/title text lives in the workspace shadow tree.
    sid_text = speaker_workspace_text(page)
    assert "Speaker" in sid_text
    assert "SPEAKER_" in sid_text or "Assign name" in sid_text or "Name" in sid_text

    fill_assign_name(page, _DISPLAY_NAME)
    after_save = speaker_workspace_text(page)
    assert (
        "Named" in after_save
        or _DISPLAY_NAME in after_save
        or "SPEAKER_01" in after_save
    )

    # Re-hydrate subject/run context, then open Transcript VIEW.
    select_transcript(page, needle="planning")
    nav(page, "Transcript")
    wait(page, 4000)
    transcript_text = page_text(page)
    assert not transcript_text.startswith("Speaker Identification")
    assert "Library\n" not in transcript_text[:40]
    assert "Transcript" in transcript_text or "SPEAKER_" in transcript_text
    assert _DISPLAY_NAME in transcript_text, (
        f"Expected display name {_DISPLAY_NAME!r} on Transcript; "
        f"got head={transcript_text[:800]!r}"
    )
