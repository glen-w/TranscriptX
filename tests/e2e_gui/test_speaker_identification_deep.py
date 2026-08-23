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

# Distinctive sample lines from docs/workflows/fixtures/planning_review.json.
_SPEAKER_LINES = {
    0: "launch planning review",
    1: "feature cut before we leave",
    2: "early access users",
}


def _assert_active_speaker_lines(page, index: int) -> str:
    """Assert heading + sample lines belong to the expected diarized speaker."""
    heading = active_speaker_heading(page)
    expect_id = f"SPEAKER_0{index}"
    expect_ord = f"{index + 1} /"
    assert expect_id in heading or expect_ord in heading, heading
    body = page_text(page)
    needle = _SPEAKER_LINES[index]
    assert needle in body, f"missing {needle!r} for {expect_id}; head={body[:900]!r}"
    # Other speakers' distinctive openers must not remain after a switch.
    for other, other_needle in _SPEAKER_LINES.items():
        if other == index:
            continue
        assert other_needle not in body, (
            f"stale lines for SPEAKER_0{other} still visible after selecting "
            f"{expect_id}: {other_needle!r}"
        )
    return body


def test_speaker_switch_next_prev_and_jump(seeded_run_app, page) -> None:
    """Next / Prev / Jump change the active diarized speaker and sample lines."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    _assert_active_speaker_lines(page, 0)

    click_speaker_nav(page, "next")
    _assert_active_speaker_lines(page, 1)

    click_speaker_nav(page, "prev")
    _assert_active_speaker_lines(page, 0)

    jump_to_speaker_index(page, 2)
    _assert_active_speaker_lines(page, 2)

    jump_to_speaker_index(page, 1)
    _assert_active_speaker_lines(page, 1)


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
    _assert_active_speaker_lines(page, 0)

    play_first_clip(page)
    assert_playback_available(page)
    assert_clip_player_mounted(page)

    # Selecting another speaker must refresh lines *and* reload that speaker's clips.
    click_speaker_nav(page, "next")
    body = _assert_active_speaker_lines(page, 1)
    assert_playback_available(page)
    play_first_clip(page)
    assert_playback_available(page)
    assert_clip_player_mounted(page)
    assert "feature cut before we leave" in body

    # Jump (click another speaker in the picker) must also swap lines + clips.
    jump_to_speaker_index(page, 2)
    _assert_active_speaker_lines(page, 2)
    assert_playback_available(page)
    play_first_clip(page)
    assert_clip_player_mounted(page)
