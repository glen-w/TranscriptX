"""Deep Speaker Identification E2E: switch, rename, ignore, load clips (CCv2)."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    active_speaker_heading,
    assert_clip_player_mounted,
    assert_clip_src_ready,
    click_load_more_samples,
    sample_play_count,
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
    speaker_workspace_text,
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
    # Classic: "Speaker 1 / 3"; CCv2 status: "1/3 · …"
    expect_ord_classic = f"{index + 1} /"
    expect_ord_ccv2 = f"{index + 1}/"
    assert (
        expect_id in heading
        or expect_ord_classic in heading
        or expect_ord_ccv2 in heading
    ), heading
    # Sample lines live in the CCv2 shadow tree — use workspace text, not stMain.
    body = speaker_workspace_text(page)
    needle = _SPEAKER_LINES[index]
    assert needle in body, f"missing {needle!r} for {expect_id}; head={body[:900]!r}"
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
    assert (
        "SPEAKER_00" in heading_before
        or "1 /" in heading_before
        or "1/" in heading_before
    )

    fill_assign_name(page, display)
    after = speaker_workspace_text(page)
    assert display in after or "Named" in after or "SPEAKER_01" in after

    heading_after = active_speaker_heading(page)
    assert heading_after != heading_before or display in after

    select_transcript(page, needle="planning")
    from tests.e2e_gui.helpers import nav

    nav(page, "Transcript")
    wait(page, 4000)
    transcript = page_text(page)
    assert display in transcript, transcript[:800]


def test_speaker_ignore_and_unignore(seeded_run_app, page) -> None:
    """Ignore marks a speaker, advances, and toggling Ignore again restores it."""
    goto_app(page, seeded_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    before = active_speaker_heading(page)
    click_ignore_speaker(page)
    body = speaker_workspace_text(page)
    assert (
        "Ignored" in body
        or "ignored" in body.lower()
        or "Unignore" in body
        or "🔇" in body
        or "SPEAKER_01" in body
    ), body[:800]

    after_ignore = active_speaker_heading(page)
    assert (
        after_ignore != before
        or "Ignored" in body
        or "Unignore" in body
        or "🔇" in body
    )

    # Jump back to the first speaker and clear ignore (CCv2 toggles Ignore;
    # classic shows an Unignore button).
    jump_to_speaker_index(page, 0)
    wait(page, 2000)
    body2 = speaker_workspace_text(page)
    ignored = (
        "Unignore" in body2
        or "ignored" in body2.lower()
        or "🔇" in body2
    )
    if ignored:
        click_unignore_speaker(page)
        restored = speaker_workspace_text(page)
        assert "Unignore" not in restored
        # CCv2 keeps a single Ignore button; ignored badge should clear.
        assert "🔇" not in restored or "ignored" not in restored.lower()


def test_speaker_clip_load_and_play(seeded_audio_run_app, page) -> None:
    """With linked audio, clip playback loads without unavailable banners."""
    goto_app(page, seeded_audio_run_app.base_url)
    open_speaker_identification(page, needle="planning")

    assert_playback_available(page)
    _assert_active_speaker_lines(page, 0)

    play_first_clip(page)
    assert_playback_available(page)
    assert_clip_player_mounted(page)
    assert_clip_src_ready(page)

    # Selecting another speaker must refresh lines *and* reload that speaker's clips.
    click_speaker_nav(page, "next")
    body = _assert_active_speaker_lines(page, 1)
    assert_playback_available(page)
    play_first_clip(page)
    assert_playback_available(page)
    assert_clip_player_mounted(page)
    assert "feature cut before we leave" in body

    # Jump (click another speaker in the list) must also swap lines + clips.
    jump_to_speaker_index(page, 2)
    _assert_active_speaker_lines(page, 2)
    assert_playback_available(page)
    play_first_clip(page)
    assert_clip_player_mounted(page)


def test_speaker_load_more_lines(seeded_audio_run_app, page) -> None:
    """CCv2 Show-more reveals additional sample lines for a long-talking speaker."""
    goto_app(page, seeded_audio_run_app.base_url)
    open_speaker_identification(page, needle="planning")
    _assert_active_speaker_lines(page, 0)
    before = sample_play_count(page)
    click_load_more_samples(page)
    after = sample_play_count(page)
    assert after > before, f"expected more sample play buttons ({before} -> {after})"
    body = speaker_workspace_text(page)
    assert "Show" not in body or after >= before

