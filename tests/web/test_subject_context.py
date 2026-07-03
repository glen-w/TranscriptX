"""Tests for transcript context resolution and SubjectService session helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    resolve_transcript_context,
)

_LEGACY_TRANSCRIPT_PATH_KEY = "selected_transcript_path"


@pytest.mark.unit
def test_resolve_slug_without_run_does_not_call_session_resolver(
    monkeypatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "interview.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {
            "transcripts": {
                "key-1": {
                    "slug": "interview",
                    "source_path": str(transcript),
                    "runs": [],
                }
            }
        },
    )
    called = {"count": 0}

    def _session_resolver(_path: str) -> tuple[str, str] | None:
        called["count"] += 1
        return ("interview", "run-1")

    result = resolve_transcript_context(
        transcript,
        session_resolver=_session_resolver,
    )

    assert result.subject_id == "interview"
    assert result.run_id is None
    assert called["count"] == 0


@pytest.mark.unit
def test_resolve_uses_linked_run_dirs_mtime(monkeypatch, tmp_path: Path) -> None:
    transcript = tmp_path / "call.json"
    transcript.write_text("{}", encoding="utf-8")
    older = tmp_path / "runs" / "20260101_120000"
    newer = tmp_path / "runs" / "20260102_120000"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    older.touch()
    (newer / "marker.txt").write_text("x", encoding="utf-8")
    import os

    os.utime(older, (1_000_000_000, 1_000_000_000))
    os.utime(newer, (2_000_000_000, 2_000_000_000))

    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {"transcripts": {}},
    )

    result = resolve_transcript_context(
        transcript,
        slug_hint="call",
        linked_run_dirs=[older, newer],
    )

    assert result.subject_id == "call"
    assert result.run_id == "20260102_120000"


@pytest.mark.unit
def test_resolve_tolerant_path_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "gone.json"
    result = resolve_transcript_context(missing)
    assert result.subject_id.endswith("gone.json")
    assert result.run_id is None


@pytest.mark.unit
def test_resolve_falls_back_to_session_resolver_when_no_slug(
    monkeypatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "orphan.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {"transcripts": {}},
    )

    result = resolve_transcript_context(
        transcript,
        session_resolver=lambda _p: ("slug-orphan", "run-9"),
    )

    assert result.subject_id == "slug-orphan"
    assert result.run_id == "run-9"


@pytest.mark.unit
def test_setter_writes_canonical_keys_and_pops_legacy() -> None:
    session_state = {_LEGACY_TRANSCRIPT_PATH_KEY: "/tmp/legacy.json"}

    SubjectService.set_transcript_context_from_path(
        session_state,
        "/tmp/new.json",
        slug_hint="new-slug",
    )

    assert session_state["subject_type"] == "transcript"
    assert session_state["subject_id"] == "new-slug"
    assert session_state["run_id"] is None
    assert _LEGACY_TRANSCRIPT_PATH_KEY not in session_state


@pytest.mark.unit
def test_index_in_path_options_matches_canonical_path(
    monkeypatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "pick.json"
    transcript.write_text("{}", encoding="utf-8")
    session_state: dict[str, object] = {}

    SubjectService.set_transcript_context_from_path(session_state, transcript)

    options = [str(tmp_path / "other.json"), str(transcript)]
    assert SubjectService.index_in_path_options(session_state, options) == 2
