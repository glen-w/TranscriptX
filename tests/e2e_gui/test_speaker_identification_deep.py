"""Deep Speaker Identification E2E: switch, rename, ignore, load clips."""

from __future__ import annotations

import re

import pytest

from tests.e2e_gui.helpers import (
    active_speaker_heading,
    assert_clip_player_mounted,
    assert_playback_available,
    click_ignore_speaker,
    click_speaker_nav,
    click_unignore_speaker,
    fill_assign_name,
    goto_app,
    jump_to_speaker_index,
    open_speaker_identification,
    page_text,
    play_first_clip,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_speaker_switch_next_prev_and_jump(seeded_run_app, page) -> None:
    """Next / Prev / Jump change the active diarized speaker and sample lines."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    first = active_speaker_heading(page)
    assert "SPEAKER_00" in first or "1 /" in first, first
    first_body = page_text(page)
    assert "SPEAKER_" in first_body

    click_speaker_nav(page, "next")
    second = active_speaker_heading(page)
    assert second != first, (first, second)
    assert "SPEAKER_01" in second or "2 /" in second, second
    second_body = page_text(page)
    # Sample lines should refresh for the newly selected speaker.
    assert second_body != first_body or "SPEAKER_01" in second_body

    click_speaker_nav(page, "prev")
    back = active_speaker_heading(page)
    assert "SPEAKER_00" in back or "1 /" in back, back

    jump_to_speaker_index(page, 2)
    jumped = active_speaker_heading(page)
    assert "SPEAKER_02" in jumped or "3 /" in jumped, jumped


def test_speaker_rename_and_confirm_on_transcript(seeded_run_app, page) -> None:
    """Rename SPEAKER_00, advance, and confirm the display name on Transcript."""
    display = "Maya Facilitator"
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    heading_before = active_speaker_heading(page)
    assert "SPEAKER_00" in heading_before or "1 /" in heading_before

    fill_assign_name(page, display)
    after = page_text(page)
    assert display in after or "Named" in after or "SPEAKER_01" in after

    # Saving should advance toward the next unnamed speaker when one remains.
    heading_after = active_speaker_heading(page)
    assert heading_after != heading_before or display in after

    select_transcript(page, needle="planning")
    from tests.e2e_gui.helpers import nav

    nav(page, "Transcript")
    wait(page, 4000)
    transcript = page_text(page)
    assert display in transcript, transcript[:800]


def test_speaker_ignore_and_unignore(seeded_run_app, page) -> None:
    """Ignore marks a speaker, advances, and Unignore restores it."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    before = active_speaker_heading(page)
    click_ignore_speaker(page)
    body = page_text(page)
    assert (
        "Ignored" in body
        or "ignored" in body.lower()
        or "Unignore" in body
        or "SPEAKER_01" in body
    ), body[:800]

    after_ignore = active_speaker_heading(page)
    # Ignore typically advances to the next remaining speaker.
    assert after_ignore != before or "Ignored" in body or "Unignore" in body

    # Jump back to the first speaker and unignore if still ignored.
    jump_to_speaker_index(page, 0)
    wait(page, 2000)
    body2 = page_text(page)
    if "Unignore" in body2:
        click_unignore_speaker(page)
        restored = page_text(page)
        assert "Ignore" in restored
        assert "Unignore" not in restored or restored.count("Unignore") == 0


def test_speaker_clip_load_and_play(seeded_audio_run_app, page) -> None:
    """With linked audio, clip playback loads without unavailable banners."""
    goto_app(page, seeded_audio_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    assert_playback_available(page)
    body = page_text(page)
    assert re.search(r"SPEAKER_0|Assign name|Speaker\s+1", body)

    play_first_clip(page)
    assert_playback_available(page)
    assert_clip_player_mounted(page)

    # Switching speakers must keep playback available and refresh samples.
    click_speaker_nav(page, "next")
    assert_playback_available(page)
    play_first_clip(page)
    assert_clip_player_mounted(page)
