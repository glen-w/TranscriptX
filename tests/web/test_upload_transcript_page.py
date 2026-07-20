"""
Tests for Import Transcript page module (web/page_modules/upload_transcript.py).
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.io.admit_and_register import AdmitOutcome, AdmitOutcomeKind


def test_import_transcript_page_exposes_renderer() -> None:
    from transcriptx.web.page_modules.upload_transcript import (
        render_upload_transcript_page,
    )

    assert callable(render_upload_transcript_page)


def test_import_uploaded_transcript_uses_admit_and_register(
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

    called = {}

    def _fake_admit(path, *, logical_basename=None, **kwargs):
        called["path"] = path
        called["logical_basename"] = logical_basename
        called.update(kwargs)
        return AdmitOutcome(
            kind=AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
            transcript_path=json_artifact,
            slug="meeting_slug",
            artifact_committed=True,
            registration_progressed=True,
            user_safe_detail="ok",
        )

    monkeypatch.setattr(mod, "admit_and_register", _fake_admit)
    monkeypatch.setattr(mod, "_clear_import_caches", lambda: None)
    monkeypatch.setattr(mod.st, "session_state", {}, raising=False)

    kind = mod._import_uploaded_transcript(uploaded)
    assert kind is AdmitOutcomeKind.IMPORTED_AND_REGISTERED
    assert called["path"] == saved_source
    assert called["logical_basename"] == "incoming.vtt"
    assert called["allow_provenance_backfill"] is True


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
        mod,
        "admit_and_register",
        lambda *a, **k: AdmitOutcome(
            kind=AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
            transcript_path=json_artifact,
            slug="slug",
            artifact_committed=True,
            registration_progressed=True,
            user_safe_detail="ok",
        ),
    )
    monkeypatch.setattr(mod, "_clear_import_caches", lambda: None)
    monkeypatch.setattr(mod.st, "session_state", {}, raising=False)

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_persist_imported_speaker_names" not in source
    assert "apply_speaker_map_on_import" not in source

    mod._import_uploaded_transcript(uploaded)


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
    assert "Import all from folder" in source
    assert "ThreadPoolExecutor" not in source
    assert "on_click=_on_scan_folder" in source


def test_on_scan_folder_stores_handle_before_import_button_can_read_it(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Scan must land in session state via on_click (prefix of the click rerun)."""
    import transcriptx.web.page_modules.upload_transcript as mod
    from transcriptx.io.folder_import import (
        CandidateStatus,
        FolderImportCandidate,
        ScanHandle,
    )

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    handle = ScanHandle(
        schema_version=1,
        admission_policy_version=1,
        resolved_folder=str(inbox),
        resolved_transcripts_root=str(tmp_path / "transcripts"),
        max_file_bytes=10_000_000,
        max_candidates=500,
        scan_id="abc",
        scanned_at="2026-01-01T00:00:00+00:00",
        closed_ok=True,
        error=None,
        candidates=(
            FolderImportCandidate(
                path=str(inbox / "a.json"),
                basename="a.json",
                display_stem="a",
                conflict_key="a",
                status=CandidateStatus.NEW,
            ),
        ),
    )

    session: dict = {mod._KEY_FOLDER_PATH: str(inbox)}
    monkeypatch.setattr(mod.st, "session_state", session, raising=False)
    monkeypatch.setattr(mod, "scan_folder_for_import", lambda path: handle)

    mod._on_scan_folder()

    stored = ScanHandle.from_session_dict(session.get(mod._KEY_SCAN_HANDLE))
    assert stored is not None
    assert stored.closed_ok
    assert len(mod.eligible_candidates(stored)) == 1
    assert session[mod._KEY_SCAN_BANNER][0] == "success"
    assert "1 eligible" in session[mod._KEY_SCAN_BANNER][1]


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
        "Groups",
    ]

    import transcriptx.web.sidebar as sidebar_mod

    source = Path(sidebar_mod.__file__).read_text(encoding="utf-8")
    workflow_start = source.index("tx_sidebar_workflow_nav")
    tools_group_idx = source.index("tx_sidebar_tools_group")
    assert workflow_start < tools_group_idx
