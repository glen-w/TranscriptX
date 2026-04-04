from __future__ import annotations

from pathlib import Path


def test_normalize_and_validate_target_name() -> None:
    from transcriptx.web.services.rename_service import RenameService

    assert RenameService.normalize_base_name("meeting.json") == "meeting"
    assert RenameService.normalize_base_name("recording.wav") == "recording"
    assert RenameService.normalize_base_name("  sample  ") == "sample"

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

    def _fake_rename(old_name: str, new_name: str, transcript_path: str) -> bool:
        calls["args"] = (old_name, new_name, transcript_path)
        return True

    monkeypatch.setattr(
        "transcriptx.web.services.rename_service.rename_transcript_files",
        _fake_rename,
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
        "transcriptx.web.services.rename_service.clear_transcript_listing_caches",
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
