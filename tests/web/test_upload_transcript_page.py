"""
Tests for Import Transcript page module (web/page_modules/upload_transcript.py).
"""

from __future__ import annotations

from pathlib import Path


def test_import_transcript_page_exposes_renderer() -> None:
    from transcriptx.web.page_modules.upload_transcript import (
        render_upload_transcript_page,
    )

    assert callable(render_upload_transcript_page)


def test_import_uploaded_transcript_builds_session_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    uploaded = object()
    saved_source = tmp_path / "incoming.vtt"
    json_artifact = tmp_path / "meeting.json"
    run_dir = tmp_path / "outputs" / "meeting_slug" / "run123"

    monkeypatch.setattr(
        mod, "_save_uploaded_transcript", lambda f: (saved_source, "incoming.vtt")
    )

    class _ManagedResult:
        json_path = json_artifact

    called = {}

    def _fake_managed(path, *, logical_upload_basename=None, **kwargs):
        called["path"] = path
        called["logical_upload_basename"] = logical_upload_basename
        called.update(kwargs)
        return _ManagedResult()

    monkeypatch.setattr(
        "transcriptx.web.page_modules.upload_transcript.run_managed_import_workflow",
        _fake_managed,
    )
    monkeypatch.setattr(
        mod,
        "_register_uploaded_transcript",
        lambda p: ("meeting_slug", "run123", run_dir),
    )
    monkeypatch.setattr(mod, "_persist_imported_speaker_names", lambda _p: None)

    session_id, out_dir, transcript_path = mod._import_uploaded_transcript(uploaded)
    assert session_id == "meeting_slug/run123"
    assert out_dir == run_dir
    assert transcript_path == json_artifact
    assert called["path"] == saved_source
    assert called["logical_upload_basename"] == "incoming.vtt"
    assert called["overwrite"] is False
    assert called["delete_staging_on_success"] is True


def test_build_speaker_map_from_segments_uses_original_speaker() -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "a",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_00",
            "text": "b",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_01",
            "text": "c",
            "original_cue": {"original_speaker": "Bob"},
        },
    ]

    mapped = mod._build_speaker_map_from_segments(segments)
    assert mapped == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


def test_persist_imported_speaker_names_calls_bulk_update(
    monkeypatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    transcript_path = tmp_path / "meeting.json"
    transcript_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_load_segments_from_json",
        lambda _p: [
            {
                "speaker": "SPEAKER_00",
                "original_cue": {"original_speaker": "Alice"},
                "text": "x",
            }
        ],
    )

    called = {"args": None, "kwargs": None}

    class _DummyMappingService:
        def bulk_update(self, *args, **kwargs):
            called["args"] = args
            called["kwargs"] = kwargs
            return None

    monkeypatch.setattr(
        "transcriptx.services.speaker_studio.mapping_service.SpeakerMappingService",
        _DummyMappingService,
    )

    mod._persist_imported_speaker_names(transcript_path)
    assert called["args"] is not None
    assert called["args"][0] == str(transcript_path)
    assert called["kwargs"]["speaker_map"] == {"SPEAKER_00": "Alice"}
    assert called["kwargs"]["ignored_speakers"] == []


def test_import_uploaded_transcript_persists_imported_speaker_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    uploaded = object()
    saved_source = tmp_path / "incoming.html"
    json_artifact = tmp_path / "meeting.json"
    run_dir = tmp_path / "outputs" / "meeting_slug" / "run123"

    monkeypatch.setattr(
        mod, "_save_uploaded_transcript", lambda f: (saved_source, "incoming.html")
    )

    class _ManagedResult:
        json_path = json_artifact

    monkeypatch.setattr(
        "transcriptx.web.page_modules.upload_transcript.run_managed_import_workflow",
        lambda path, **kwargs: _ManagedResult(),
    )
    monkeypatch.setattr(
        mod,
        "_register_uploaded_transcript",
        lambda p: ("meeting_slug", "run123", run_dir),
    )

    called = {"path": None}
    monkeypatch.setattr(
        mod,
        "_persist_imported_speaker_names",
        lambda p: called.__setitem__("path", p),
    )

    session_id, out_dir, transcript_path = mod._import_uploaded_transcript(uploaded)
    assert session_id == "meeting_slug/run123"
    assert out_dir == run_dir
    assert called["path"] == json_artifact
    assert transcript_path == json_artifact


def test_save_uploaded_recording_uses_recordings_service(monkeypatch) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    uploaded = object()
    expected = Path("/tmp/recordings/imports/audio.wav")
    called = {"value": False}

    def _fake_save(file_obj):
        called["value"] = True
        assert file_obj is uploaded
        return expected

    monkeypatch.setattr(mod.RecordingsService, "save_uploaded_file", _fake_save)

    actual = mod._save_uploaded_recording(uploaded)
    assert called["value"] is True
    assert actual == expected


def test_clear_import_caches_clears_transcript_recording_and_streamlit(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    called = {"listing_caches": 0, "recordings": 0}

    def _fake_clear_listing_caches() -> None:
        called["listing_caches"] += 1

    class _DummyRecordingsList:
        @staticmethod
        def clear():
            called["recordings"] += 1

    class _DummyRecordingsService:
        list_recordings = _DummyRecordingsList()

    monkeypatch.setattr(
        mod,
        "clear_transcript_listing_caches",
        _fake_clear_listing_caches,
    )
    monkeypatch.setattr(mod, "RecordingsService", _DummyRecordingsService)

    mod._clear_import_caches()
    assert called == {"listing_caches": 1, "recordings": 1}


def test_import_page_contains_no_auto_transcription_message() -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "does not transcribe audio" in source
    assert "A transcript file is still required for transcript text content." in source
    assert "Rename imported transcript + linked audio" in source


def test_app_workflow_menu_order_under_workflow() -> None:
    import transcriptx.web.app as app_mod

    source = Path(app_mod.__file__).read_text(encoding="utf-8")
    workflow_idx = source.index('_section("Workflow")')
    transcribe_idx = source.index('_nav_button("Transcribe Audio", "Transcribe Audio")')
    import_idx = source.index('_nav_button("Import Transcript", "Import Transcript")')
    speaker_idx = source.index('_nav_button("Speaker ID", "Speaker Identification")')
    run_analysis_idx = source.index('_nav_button("Run Analysis", "Run Analysis")')
    batch_idx = source.index('_nav_button("Batch Ops", "Batch Analysis")')
    groups_idx = source.index('_nav_button("Groups", "Groups")')
    tools_idx = source.index('_section("Tools")')
    assert (
        workflow_idx
        < transcribe_idx
        < import_idx
        < speaker_idx
        < run_analysis_idx
        < batch_idx
        < groups_idx
        < tools_idx
    )
