"""Tests for cross-session analysis-in-progress locks."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from transcriptx.core.utils.analysis_locks import (
    AnalysisBusyError,
    analysis_lock_held,
    group_analysis_lock,
    transcript_analysis_lock,
)


def test_transcript_lock_excludes_other_thread(tmp_path: Path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    state_dir = tmp_path / "state"
    held = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with transcript_analysis_lock(transcript, state_dir=state_dir):
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=_holder, name="tx-lock-holder")
    worker.start()
    assert held.wait(timeout=5)
    with pytest.raises(AnalysisBusyError) as exc:
        with transcript_analysis_lock(transcript, state_dir=state_dir):
            pass
    assert exc.value.kind == "transcript"
    assert analysis_lock_held(
        kind="transcript", identity=str(transcript), state_dir=state_dir
    )
    release.set()
    worker.join(timeout=5)
    assert not analysis_lock_held(
        kind="transcript", identity=str(transcript), state_dir=state_dir
    )


def test_group_lock_excludes_other_thread(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    held = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with group_analysis_lock("group-uuid", state_dir=state_dir):
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=_holder)
    worker.start()
    assert held.wait(timeout=5)
    with pytest.raises(AnalysisBusyError) as exc:
        with group_analysis_lock("group-uuid", state_dir=state_dir):
            pass
    assert "group" in str(exc.value).lower()
    release.set()
    worker.join(timeout=5)
