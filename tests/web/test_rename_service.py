from __future__ import annotations

from pathlib import Path


def test_normalize_and_validate_target_name() -> None:
    from transcriptx.web.services.rename_service import RenameService

    assert RenameService.normalize_base_name("meeting.json") == "meeting"
    assert RenameService.normalize_base_name("recording.wav") == "recording"
    assert RenameService.normalize_base_name("  sample  ") == "sample"
    assert RenameService.normalize_base_name("  talk.MP3  ") == "talk"
    assert RenameService.normalize_base_name("clip.flac") == "clip"
    assert RenameService.normalize_base_name("noext") == "noext"

    ok, msg = RenameService.validate_target_name("old_name", "old_name")
    assert ok is False
    assert "different" in msg

    ok, msg = RenameService.validate_target_name("old_name", "bad/name")
    assert ok is False
    assert "invalid characters" in msg

    ok, msg = RenameService.validate_target_name("old_name", "new_name")
    assert ok is True
    assert msg == ""


def test_rename_transcript_and_audio_uses_core_rename(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.web.services.rename_service import RenameService

    transcript = tmp_path / "old_name.json"
    transcript.write_text("{}", encoding="utf-8")

    calls = {"args": None}

    def _fake_outcome(
        old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
    ):
        from transcriptx.core.utils.file_rename import RenameTranscriptOutcome

        calls["args"] = (old_name, new_name, transcript_path)
        return RenameTranscriptOutcome(
            transaction_attempted=True,
            transaction_succeeded=True,
            transaction_committed=True,
            finalize_attempted=False,
            finalize_succeeded=True,
        )

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.rename_transcript_files_with_outcome",
        _fake_outcome,
    )
    monkeypatch.setattr(
        RenameService,
        "_find_audio_path_for_transcript",
        staticmethod(lambda _tp: None),
    )

    result = RenameService.rename_transcript_and_audio(transcript, "new_name")
    assert result.ok is True
    assert calls["args"] == ("old_name", "new_name", str(transcript))
    assert result.new_transcript_path.endswith("new_name.json")


def test_find_linked_transcript_for_audio_reads_processing_state(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.web.services.rename_service import RenameService

    transcript = tmp_path / "sample.json"
    transcript.write_text("{}", encoding="utf-8")
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"audio")

    state = {
        "processed_files": {
            "abc": {"transcript_path": str(transcript), "mp3_path": str(audio)}
        }
    }
    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.load_processing_state",
        lambda validate=False: state,
    )
    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.find_original_audio_file",
        lambda tp: audio if tp == str(transcript) else None,
    )

    found = RenameService.find_linked_transcript_for_audio(audio)
    assert found == transcript


def test_refresh_after_rename_updates_state_and_caches(monkeypatch) -> None:
    from transcriptx.web.services.rename_service import RenameResult, RenameService

    calls = {"listing_caches": 0, "recordings": 0}

    def _fake_clear_listing_caches() -> None:
        calls["listing_caches"] += 1

    class _DummyRecordings:
        @staticmethod
        def clear() -> None:
            calls["recordings"] += 1

    class _DummyStreamlit:
        session_state = {
            "selected_transcript_path": "/tmp/old.json",
            "subject_id": "/tmp/old.json",
            "run_id": "run_1",
            "audio_prep_selected_file": "/tmp/old.mp3",
            "audio_prep_selected_files": ["/tmp/old.mp3", "/tmp/other.mp3"],
            "audio_merge_ordered_paths": ["/tmp/old.mp3"],
        }

    class _DummyService:
        list_recordings = _DummyRecordings()

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.clear_rename_related_caches",
        _fake_clear_listing_caches,
    )
    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.RecordingsService", _DummyService
    )
    monkeypatch.setattr("transcriptx.web.services.rename_service.st", _DummyStreamlit())

    RenameService.refresh_after_rename(
        RenameResult(
            ok=True,
            message="ok",
            old_transcript_path="/tmp/old.json",
            new_transcript_path="/tmp/new.json",
            old_audio_path="/tmp/old.mp3",
            new_audio_path="/tmp/new.mp3",
        )
    )

    assert calls == {"listing_caches": 1, "recordings": 1}
    assert _DummyStreamlit.session_state["selected_transcript_path"] == "/tmp/new.json"
    assert _DummyStreamlit.session_state["subject_id"] == "/tmp/new.json"
    assert _DummyStreamlit.session_state["run_id"] is None
    assert _DummyStreamlit.session_state["audio_prep_selected_file"] == "/tmp/new.mp3"
    assert (
        _DummyStreamlit.session_state["audio_prep_selected_files"][0] == "/tmp/new.mp3"
    )
    assert (
        _DummyStreamlit.session_state["audio_merge_ordered_paths"][0] == "/tmp/new.mp3"
    )


def test_after_rename_patches_slug_subject_and_library_select(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.app.models.metadata import TranscriptMetadata
    from transcriptx.web.services.rename_service import RenameResult, RenameService

    old_t = str((tmp_path / "old.json").resolve())
    new_t = str((tmp_path / "new.json").resolve())
    transcripts = [
        TranscriptMetadata(path=Path(new_t), base_name="new"),
    ]

    calls = {"caches": 0}

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.clear_rename_related_caches",
        lambda: calls.__setitem__("caches", calls["caches"] + 1),
    )

    class _DummyRecordings:
        @staticmethod
        def clear() -> None:
            pass

    class _DummyStreamlit:
        session_state = {
            "selected_transcript_path": old_t,
            "subject_id": "old_name",
            "run_id": "run_1",
            "library_transcript_select": 0,
        }

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.RecordingsService",
        type("R", (), {"list_recordings": _DummyRecordings})(),
    )
    monkeypatch.setattr("transcriptx.web.services.rename_service.st", _DummyStreamlit())

    RenameService.after_rename(
        RenameResult(
            ok=True,
            message="ok",
            old_transcript_path=old_t,
            new_transcript_path=new_t,
            old_slug="old_name",
            new_slug="new_name",
        ),
        library_transcripts=transcripts,
    )

    assert calls["caches"] == 1
    assert _DummyStreamlit.session_state["selected_transcript_path"] == new_t
    assert _DummyStreamlit.session_state["subject_id"] == "new_name"
    assert _DummyStreamlit.session_state["run_id"] is None
    assert _DummyStreamlit.session_state["library_transcript_select"] == 1


def test_unified_rename_entry_point_delegates_to_transcript_path(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.web.services.rename_service import RenameResult, RenameService

    transcript = tmp_path / "a.json"
    transcript.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake(transcript_path, raw_target_name, *, dry_run: bool):
        captured["path"] = transcript_path
        captured["name"] = raw_target_name
        captured["dry_run"] = dry_run
        return RenameResult(ok=True, message="ok")

    monkeypatch.setattr(RenameService, "_rename_transcript_path", staticmethod(_fake))
    RenameService.rename(transcript_path=transcript, new_base_name="b")
    assert captured == {"path": transcript, "name": "b", "dry_run": False}


def test_rename_transcript_and_audio_returns_not_found_when_transcript_missing(
    tmp_path: Path,
) -> None:
    from transcriptx.web.services.rename_service import RenameService

    missing = tmp_path / "ghost.json"
    result = RenameService.rename_transcript_and_audio(missing, "new_name")
    assert result.ok is False
    assert "not found" in result.message.lower()


def test_rename_from_audio_returns_unlinked_message_when_no_state_match(
    tmp_path: Path, monkeypatch
) -> None:
    from transcriptx.web.services.rename_service import RenameService

    audio = tmp_path / "orphan.mp3"
    audio.write_bytes(b"x")
    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.load_processing_state",
        lambda validate=False: {"processed_files": {}},
    )
    result = RenameService.rename_from_audio(audio, "renamed")
    assert result.ok is False
    assert "not linked" in result.message.lower()


def test_rename_transcript_and_audio_partial_finalize_surfaces_distinct_message(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.core.utils.file_rename import RenameTranscriptOutcome
    from transcriptx.web.services.rename_service import RenameService

    transcript = tmp_path / "cur.json"
    transcript.write_text("{}", encoding="utf-8")

    def _partial_outcome(
        old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
    ) -> RenameTranscriptOutcome:
        return RenameTranscriptOutcome(
            transaction_attempted=True,
            transaction_succeeded=True,
            transaction_committed=True,
            finalize_attempted=True,
            finalize_succeeded=False,
            last_error="simulated",
        )

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.rename_transcript_files_with_outcome",
        _partial_outcome,
    )
    monkeypatch.setattr(
        RenameService,
        "_find_audio_path_for_transcript",
        staticmethod(lambda _tp: None),
    )

    result = RenameService.rename_transcript_and_audio(transcript, "new_base")
    assert result.ok is False
    assert result.transaction_phase_ok is True
    assert result.finalize_phase_ok is False
    assert "output" in result.message.lower() and "folder" in result.message.lower()


def test_find_audio_path_for_transcript_delegates_to_core_lookup(
    tmp_path: Path, monkeypatch
) -> None:
    from transcriptx.web.services.rename_service import RenameService

    transcript = tmp_path / "meet.json"
    transcript.write_text("{}", encoding="utf-8")
    wav = tmp_path / "via_audio.wav"
    wav.write_bytes(b"a")

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.find_original_audio_file",
        lambda tp: wav if tp == str(transcript) else None,
    )

    found = RenameService._find_audio_path_for_transcript(transcript)
    assert found == wav
