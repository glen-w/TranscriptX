"""
Tests for target resolution: file-mode (path) never touches DB.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
    TranscriptRef,
    resolve_analysis_target,
)


class TestResolveAnalysisTargetFilePath:
    """File path resolution returns file-only member and never touches DB."""

    def test_resolve_path_returns_scope_and_file_member(self, tmp_path: Path) -> None:
        transcript_file = tmp_path / "some" / "nested" / "transcript.json"
        transcript_file.parent.mkdir(parents=True, exist_ok=True)
        transcript_file.write_text("{}")

        scope, members = resolve_analysis_target(TranscriptRef(path=str(transcript_file)))

        assert isinstance(scope, AnalysisScope)
        assert scope.scope_type == "transcript"
        assert scope.display_name == "transcript"
        assert len(members) == 1
        member = members[0]
        assert isinstance(member, FileTranscriptMember)
        assert member.file_path == str(transcript_file.resolve())
        assert member.file_name == "transcript.json"
        assert member.id is None
        assert member.uuid is not None
        assert member.source == "file"

    def test_resolve_path_normalizes_and_uses_stem_for_display(self, tmp_path: Path) -> None:
        transcript_file = tmp_path / "my.transcript.json"
        transcript_file.write_text("{}")

        scope, members = resolve_analysis_target(TranscriptRef(path=str(transcript_file)))

        assert scope.display_name == "my.transcript"
        assert members[0].file_name == "my.transcript.json"
        assert members[0].file_path == str(transcript_file.resolve())

    @pytest.mark.parametrize("db_enabled", ["0", "1"])
    def test_resolve_path_never_touches_db(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_enabled: str
    ) -> None:
        """With path target, get_session and get_transcript_file_by_path must never be called."""
        monkeypatch.setenv("TRANSCRIPTX_DB_ENABLED", db_enabled)
        transcript_file = tmp_path / "file_mode.json"
        transcript_file.write_text("{}")

        get_session_raised: list[str] = []
        get_by_path_raised: list[str] = []

        def raise_if_get_session(*args: object, **kwargs: object) -> None:
            get_session_raised.append("called")
            raise RuntimeError("get_session must not be called for path targets")

        def raise_if_get_by_path(*args: object, **kwargs: object) -> None:
            get_by_path_raised.append("called")
            raise RuntimeError("get_transcript_file_by_path must not be called for path targets")

        with (
            patch(
                "transcriptx.core.pipeline.target_resolver.get_session",
                side_effect=raise_if_get_session,
            ),
            patch(
                "transcriptx.database.repositories.transcript.TranscriptFileRepository.get_transcript_file_by_path",
                side_effect=raise_if_get_by_path,
            ),
        ):
            scope, members = resolve_analysis_target(TranscriptRef(path=str(transcript_file)))

        assert get_session_raised == [], "path target must not call get_session"
        assert get_by_path_raised == [], "path target must not call get_transcript_file_by_path"
        assert len(members) == 1 and members[0].file_path == str(transcript_file.resolve())
