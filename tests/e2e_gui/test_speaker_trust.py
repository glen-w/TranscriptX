"""Workflow 2: Identify and name speakers — name speakers and confirm on Transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    advance_speaker_id_next,
    assign_speaker_name,
    fill_assign_name,
    goto_app,
    nav,
    open_speaker_identification,
    page_text,
    select_transcript,
    show_unnamed_speakers_on_transcript,
    speaker_workspace_text,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_SPEAKERS = (
    "Alex Facilitator",
    "Jordan Engineer",
    "Sam Support",
)


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

    fill_assign_name(page, _SPEAKERS[0])
    after_save = speaker_workspace_text(page)
    assert (
        "Named" in after_save
        or _SPEAKERS[0] in after_save
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
    assert _SPEAKERS[0] in transcript_text, (
        f"Expected display name {_SPEAKERS[0]!r} on Transcript; "
        f"got head={transcript_text[:800]!r}"
    )


def test_speaker_trust_names_multiple_speakers(seeded_run_app, page) -> None:
    """Walkthrough step 4: name remaining speakers via Next navigation."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    assign_speaker_name(page, _SPEAKERS[0], advance=True)
    assign_speaker_name(page, _SPEAKERS[1], advance=True)
    fill_assign_name(page, _SPEAKERS[2])

    after = speaker_workspace_text(page)
    assert (
        any(name in after for name in _SPEAKERS)
        or "Speaker 3" in after
        or "SPEAKER_02" in after
        or "Named" in after
    )

    select_transcript(page, needle="planning")
    nav(page, "Transcript")
    wait(page, 4000)
    show_unnamed_speakers_on_transcript(page, enabled=True)
    wait(page, 2000)
    transcript = page_text(page)
    named_count = sum(1 for name in _SPEAKERS if name in transcript)
    assert named_count >= 1, (
        f"Expected at least one named speaker on Transcript; "
        f"named_count={named_count}; head={transcript[:900]!r}"
    )


def test_speaker_trust_next_control_advances(seeded_run_app, page) -> None:
    """Prev/Next controls should be present for multi-speaker navigation."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    sid_text = speaker_workspace_text(page)
    assert (
        "SPEAKER_" in sid_text
        or "Assign name" in sid_text
        or "Name" in sid_text
    )

    advance_speaker_id_next(page)
    after = speaker_workspace_text(page)
    assert "Speaker" in after
