"""Unit and integration tests for the directory watcher (G2)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from transcriptx.io.folder_import import CandidateStatus, classify_inbox_file
from transcriptx.services.watcher.classifier import WatchKind, classify_path
from transcriptx.services.watcher.job_store import JobState, JobStore
from transcriptx.services.watcher.pipeline import process_watched_path
from transcriptx.services.watcher.service import (
    DirectoryWatcherService,
    reset_watcher_service_for_tests,
)
from transcriptx.services.watcher.settings import (
    DirectoryWatcherSettings,
    load_watcher_settings,
    save_watcher_settings,
)
from transcriptx.services.watcher.stability import wait_until_stable


def _patch_import_roots(monkeypatch, transcript_root: Path, outputs: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        transcript_root / "originals",
    )
    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.TRANSCRIPTS_IMPORTS_DIR",
        transcript_root / "imports",
    )
    monkeypatch.setattr(
        "transcriptx.io.folder_import.TRANSCRIPTS_IMPORTS_DIR",
        transcript_root / "imports",
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        transcript_root / "metadata",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.INDEX_FILE",
        outputs / ".transcriptx_index.json",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.OUTPUTS_DIR",
        outputs,
    )
    (transcript_root / "originals").mkdir(parents=True, exist_ok=True)
    (transcript_root / "imports").mkdir(parents=True, exist_ok=True)
    (transcript_root / "metadata").mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)


def test_settings_default_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_WATCHER_ENABLED", raising=False)
    monkeypatch.delenv("TRANSCRIPTX_WATCHER_PATHS", raising=False)
    settings = load_watcher_settings(config_dir=tmp_path)
    assert settings.enabled is False
    assert settings.watch_paths == []
    assert settings.transcript_mode == "auto_import"
    assert settings.audio_mode == "offer"


def test_settings_env_and_file_roundtrip(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    saved = DirectoryWatcherSettings(
        enabled=False,
        watch_paths=[str(inbox)],
        debounce_ms=2500,
        transcript_mode="offer",
    )
    save_watcher_settings(saved, config_dir=tmp_path)
    monkeypatch.setenv("TRANSCRIPTX_WATCHER_ENABLED", "true")
    monkeypatch.setenv("TRANSCRIPTX_WATCHER_DEBOUNCE_MS", "3000")
    loaded = load_watcher_settings(config_dir=tmp_path)
    assert loaded.enabled is True
    assert loaded.watch_paths == [str(inbox)]
    assert loaded.debounce_ms == 3000
    assert loaded.transcript_mode == "offer"


def test_validate_for_enable_requires_paths_and_rejects_auto_transcribe() -> None:
    settings = DirectoryWatcherSettings(enabled=True, watch_paths=[])
    errs = settings.validate_for_enable()
    assert any("watch path" in e.lower() for e in errs)

    settings2 = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=["/tmp/inbox"],
        audio_mode="auto_transcribe",
    )
    errs2 = settings2.validate_for_enable()
    assert any("auto_transcribe" in e for e in errs2)


def test_classifier_extensions() -> None:
    settings = DirectoryWatcherSettings()
    assert classify_path("a.srt", settings) is WatchKind.TRANSCRIPT
    assert classify_path("a.mp3", settings) is WatchKind.AUDIO
    assert classify_path("a.bin", settings) is WatchKind.IGNORE


def test_stability_gate_growing_file(tmp_path: Path) -> None:
    path = tmp_path / "grow.srt"
    path.write_text("part1", encoding="utf-8")

    def grow() -> None:
        time.sleep(0.05)
        path.write_text("part1-part2-longer", encoding="utf-8")

    # Start growth shortly after wait begins — should not return until quiet.
    import threading

    threading.Thread(target=grow, daemon=True).start()
    identity = wait_until_stable(path, checks=2, interval_ms=40, timeout_ms=2000)
    assert identity is not None
    assert identity.size == path.stat().st_size
    assert identity.matches_current()


def test_stability_missing_file(tmp_path: Path) -> None:
    assert (
        wait_until_stable(
            tmp_path / "missing.srt", checks=1, interval_ms=10, timeout_ms=50
        )
        is None
    )


def test_classify_inbox_rejects_symlink(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    _patch_import_roots(monkeypatch, root, tmp_path / "outputs")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    real = inbox / "real.srt"
    real.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    link = inbox / "link.srt"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("symlinks not supported")
    cand = classify_inbox_file(link, transcripts_dir=root)
    assert cand.status is CandidateStatus.SYMLINK


def test_pipeline_imports_new_transcript(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    _patch_import_roots(monkeypatch, root, tmp_path / "outputs")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "meeting.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello world\n", encoding="utf-8")

    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        transcript_mode="auto_import",
        audio_mode="offer",
        debounce_ms=100,
        stability_checks=1,
        stability_interval_ms=50,
    )
    store = JobStore(tmp_path / "watcher" / "jobs")
    job = process_watched_path(src, settings=settings, store=store)
    assert job.state is JobState.IMPORTED
    assert (root / "meeting.json").is_file()
    assert list((root / "originals").glob("meeting.*"))
    assert job.transcript_path is not None


def test_pipeline_skips_already_managed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    _patch_import_roots(monkeypatch, root, tmp_path / "outputs")
    # Seed managed artifacts via a first import.
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "meeting.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello world\n", encoding="utf-8")
    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        stability_checks=1,
        stability_interval_ms=50,
    )
    store = JobStore(tmp_path / "watcher" / "jobs")
    first = process_watched_path(src, settings=settings, store=store)
    assert first.state is JobState.IMPORTED

    second = process_watched_path(src, settings=settings, store=store)
    assert second.state is JobState.SKIPPED
    assert "already_managed" in second.detail


def test_pipeline_queues_audio_in_offer_mode(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    audio = inbox / "note.mp3"
    audio.write_bytes(b"ID3fake")
    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        audio_mode="offer",
        stability_checks=1,
        stability_interval_ms=50,
    )
    store = JobStore(tmp_path / "watcher" / "jobs")
    job = process_watched_path(audio, settings=settings, store=store)
    assert job.state is JobState.QUEUED_TRANSCRIPTION
    assert job.kind == "audio"


def test_pipeline_stale_identity_fails_closed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    _patch_import_roots(monkeypatch, root, tmp_path / "outputs")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "meeting.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    # Force stability to return an outdated identity, then mutate the file.
    from transcriptx.services.watcher import stability as stability_mod
    from transcriptx.services.watcher.stability import FileIdentity

    old = FileIdentity.from_lstat(src)
    assert old is not None
    src.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello changed\n", encoding="utf-8"
    )

    def _fake_stable(*_a, **_k):
        return old

    monkeypatch.setattr(stability_mod, "wait_until_stable", _fake_stable)
    # Also patch the name used inside pipeline
    monkeypatch.setattr(
        "transcriptx.services.watcher.pipeline.wait_until_stable", _fake_stable
    )

    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        stability_checks=1,
        stability_interval_ms=50,
    )
    store = JobStore(tmp_path / "watcher" / "jobs")
    job = process_watched_path(src, settings=settings, store=store)
    assert job.state in {JobState.SKIPPED, JobState.FAILED}
    assert (
        "changed" in job.detail.lower()
        or "mismatch" in job.detail.lower()
        or "size" in job.detail.lower()
    )


def test_service_rejects_enable_without_paths(tmp_path: Path) -> None:
    reset_watcher_service_for_tests()
    service = DirectoryWatcherService(
        settings=DirectoryWatcherSettings(enabled=False),
        jobs_dir=tmp_path / "jobs",
    )
    with pytest.raises(ValueError, match="watch path"):
        service.configure(
            DirectoryWatcherSettings(enabled=True, watch_paths=[]),
            persist=False,
        )


def test_service_rejects_managed_library_path(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    monkeypatch.setattr(
        "transcriptx.services.watcher.service.resolve_transcripts_root",
        lambda transcripts_dir=None: root,
    )
    service = DirectoryWatcherService(
        settings=DirectoryWatcherSettings(enabled=False),
        jobs_dir=tmp_path / "jobs",
    )
    with pytest.raises(ValueError, match="managed transcripts"):
        service.configure(
            DirectoryWatcherSettings(enabled=True, watch_paths=[str(root / "sub")]),
            persist=False,
        )


def test_job_store_activity(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    job = store.create(path="/tmp/a.srt", basename="a.srt")
    store.update(job, state=JobState.IMPORTED, detail="ok")
    activity = store.recent_activity(limit=5)
    assert activity
    assert activity[0]["state"] == "imported"
    counts = store.counts_by_state()
    assert counts.get("imported") == 1


def test_pipeline_cancel_during_stabilize(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "meeting.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    def _slow_stable(*_a, **_k):
        time.sleep(0.2)
        from transcriptx.services.watcher.stability import FileIdentity

        return FileIdentity.from_lstat(src)

    monkeypatch.setattr(
        "transcriptx.services.watcher.pipeline.wait_until_stable", _slow_stable
    )
    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        stability_checks=1,
        stability_interval_ms=50,
    )
    store = JobStore(tmp_path / "watcher" / "jobs")
    cancelled = {"flag": False}

    def _cancel() -> bool:
        return cancelled["flag"]

    import threading

    result: dict[str, object] = {}

    def _run() -> None:
        result["job"] = process_watched_path(
            src, settings=settings, store=store, cancel_check=_cancel
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.05)
    cancelled["flag"] = True
    thread.join(timeout=5.0)
    job = result.get("job")
    assert job is not None
    assert job.state is JobState.CANCELLED  # type: ignore[union-attr]


def test_observer_debounce_fires_once(tmp_path: Path) -> None:
    from transcriptx.services.watcher.observer import _DebouncedHandler
    from transcriptx.services.watcher.settings import DirectoryWatcherSettings

    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(tmp_path)],
        debounce_ms=100,
    )
    hits: list[str] = []

    def _on(path):
        hits.append(str(path))

    handler = _DebouncedHandler(settings=settings, on_path=_on)
    target = tmp_path / "a.srt"
    target.write_text("x", encoding="utf-8")

    class _Evt:
        is_directory = False
        src_path = str(target)

    handler.on_created(_Evt())
    handler.on_modified(_Evt())
    time.sleep(0.25)
    assert hits == [str(target)]
    handler.cancel_all()


def test_classify_inbox_file_new_status(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "transcripts"
    _patch_import_roots(monkeypatch, root, tmp_path / "outputs")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "fresh.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    cand = classify_inbox_file(src, transcripts_dir=root)
    assert cand.status is CandidateStatus.NEW


def test_get_watcher_service_autostarts_when_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    reset_watcher_service_for_tests()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    settings = DirectoryWatcherSettings(
        enabled=True,
        watch_paths=[str(inbox)],
        stability_checks=1,
        stability_interval_ms=50,
    )
    save_watcher_settings(settings, config_dir=config_dir)
    monkeypatch.setenv("TRANSCRIPTX_CONFIG_DIR", str(config_dir))
    # Force settings loader to use our config dir via load path in service.
    monkeypatch.setattr(
        "transcriptx.services.watcher.service.load_watcher_settings",
        lambda: load_watcher_settings(config_dir=config_dir),
    )
    from transcriptx.services.watcher.service import get_watcher_service

    service = get_watcher_service()
    try:
        status = service.status()
        assert status.enabled is True
        assert status.running is True or status.observer_alive is True
    finally:
        service.stop()
        reset_watcher_service_for_tests()
