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
        lambda p: "meeting_slug",
    )

    slug, transcript_path = mod._import_uploaded_transcript(uploaded)
    assert slug == "meeting_slug"
    assert transcript_path == json_artifact
    assert called["path"] == saved_source
    assert called["logical_upload_basename"] == "incoming.vtt"
    assert called["overwrite"] is False
    assert called["delete_staging_on_success"] is True


def test_import_uploaded_transcript_does_not_apply_speaker_map_directly(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    uploaded = object()
    json_artifact = tmp_path / "meeting.json"

    monkeypatch.setattr(
        mod, "_save_uploaded_transcript", lambda f: (tmp_path / "x.vtt", "x.vtt")
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.upload_transcript.run_managed_import_workflow",
        lambda path, **kwargs: type("R", (), {"json_path": json_artifact})(),
    )
    monkeypatch.setattr(mod, "_register_uploaded_transcript", lambda p: "slug")

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_persist_imported_speaker_names" not in source
    assert "apply_speaker_map_on_import" not in source

    mod._import_uploaded_transcript(uploaded)


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


def test_import_page_renders_post_import_action_links() -> None:
    import transcriptx.web.page_modules.upload_transcript as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_render_post_import_actions" in source
    assert "SectionId.IMPORT_SUCCESS" in source
    assert "render_configured_actions" in source
    assert "Select it from **Library**" not in source


def test_app_workflow_menu_order_under_workflow() -> None:
    from transcriptx.web.navigation import pages_in_section

    workflow_keys = [spec.key for spec in pages_in_section("workflow")]
    assert workflow_keys == [
        "Transcribe Audio",
        "Import Transcript",
        "Speaker ID",
        "Corrections Studio",
        "Run Analysis",
        "Batch Ops",
        "Groups",
    ]

    import transcriptx.web.sidebar as sidebar_mod

    source = Path(sidebar_mod.__file__).read_text(encoding="utf-8")
    workflow_start = source.index("tx_sidebar_workflow_nav")
    tools_group_idx = source.index("tx_sidebar_tools_group")
    assert workflow_start < tools_group_idx
