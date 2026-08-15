"""Unit tests for full-workspace backup / restore."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from transcriptx.app.models.errors import BackupError
from transcriptx.core.utils.paths import PathSettings
from transcriptx.services import workspace_backup as workspace_backup_mod
from transcriptx.services.workspace_backup import (
    MANIFEST_NAME,
    BackupOptions,
    WorkspaceBackupService,
)


def _paths(tmp_path: Path) -> PathSettings:
    data = tmp_path / "data"
    config = tmp_path / "config"
    recordings = tmp_path / "recordings"
    transcripts = tmp_path / "transcripts"
    outputs = data / "outputs"
    state = data / "state"
    speaker_profiles = data / "speaker_profiles"
    wav_backup = data / "backups" / "wav"
    for path in (
        data,
        config,
        recordings,
        transcripts,
        outputs,
        state,
        speaker_profiles,
        wav_backup,
        data / "groups",
        data / "corrections",
        data / "cache",
        transcripts / "imports",
        transcripts / "metadata",
        transcripts / "originals",
        transcripts / "readable",
    ):
        path.mkdir(parents=True, exist_ok=True)
    return PathSettings(
        project_root=tmp_path,
        recordings_dir=recordings,
        recordings_imports_dir=recordings / "imports",
        transcripts_dir=transcripts,
        transcripts_imports_dir=transcripts / "imports",
        transcripts_originals_dir=transcripts / "originals",
        transcripts_metadata_dir=transcripts / "metadata",
        transcripts_speaker_maps_dir=transcripts / "metadata" / "speaker_maps",
        readable_transcripts_dir=transcripts / "readable",
        data_dir=data,
        speaker_profiles_dir=speaker_profiles,
        outputs_dir=outputs,
        group_outputs_dir=outputs / "groups",
        preprocessing_dir=data / "preprocessing",
        state_dir=state,
        processing_state_file=state / "processing_state.json",
        speaker_profiles_lock_file=state / "speaker_profiles.lock",
        config_dir=config,
        profiles_dir=config / "profiles",
        wav_backup_dir=wav_backup,
        state_backup_dir=data / "backups" / "processing_state",
        audio_playback_cache_dir=data / "cache" / "audio_playback",
        voice_cache_dir=data / "cache" / "voice",
    )


def _seed_workspace(ps: PathSettings) -> None:
    (ps.config_dir / "config.json").write_text(
        json.dumps({"schema_version": 1}), encoding="utf-8"
    )
    (ps.config_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (ps.transcripts_dir / "demo.json").write_text(
        json.dumps({"schema_version": 1, "segments": []}), encoding="utf-8"
    )
    (ps.transcripts_dir / "imports" / "staging.json").write_text(
        '{"temp": true}\n', encoding="utf-8"
    )
    (ps.transcripts_dir / ".cache" / "thumb.bin").parent.mkdir(parents=True, exist_ok=True)
    (ps.transcripts_dir / ".cache" / "thumb.bin").write_bytes(b"nope")
    (ps.data_dir / "groups" / "demo.group.json").write_text(
        json.dumps({"id": "demo"}), encoding="utf-8"
    )
    (ps.speaker_profiles_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (ps.speaker_profiles_dir / "profiles" / "p1.speaker_profile.json").write_text(
        json.dumps({"id": "p1"}), encoding="utf-8"
    )
    (ps.speaker_profiles_dir / "voice" / "samples").mkdir(parents=True, exist_ok=True)
    (ps.speaker_profiles_dir / "voice" / "samples" / "a.bin").write_bytes(b"voice")
    (ps.state_dir / "processing_state.json").write_text("{}", encoding="utf-8")
    (ps.state_dir / "speaker_profiles.lock").write_text("", encoding="utf-8")
    (ps.data_dir / "cache" / "audio_playback" / "x.bin").parent.mkdir(
        parents=True, exist_ok=True
    )
    (ps.data_dir / "cache" / "audio_playback" / "x.bin").write_bytes(b"cache")
    (ps.recordings_dir / "clip.wav").write_bytes(b"RIFF")
    (ps.outputs_dir / "old_run" / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (ps.outputs_dir / "old_run" / "manifest.json").write_text("{}", encoding="utf-8")
    (ps.wav_backup_dir / "kept.wav").write_bytes(b"wav")


def test_create_verify_excludes_cache_locks_and_imports(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    result = service.create_backup(ps, dest, BackupOptions())
    assert result.archive_path.is_file()
    assert result.transcript_count == 1

    with zipfile.ZipFile(dest) as zf:
        names = set(zf.namelist())
    assert MANIFEST_NAME in names
    assert "transcripts/demo.json" in names
    assert "config/config.json" in names
    assert "data/groups/demo.group.json" in names
    assert "data/speaker_profiles/profiles/p1.speaker_profile.json" in names
    assert "data/speaker_profiles/voice/samples/a.bin" in names
    assert "data/state/processing_state.json" in names
    assert "wav_backup/kept.wav" in names
    assert not any("imports/" in n for n in names)
    assert not any("audio_playback" in n for n in names)
    assert not any(".cache/" in n for n in names)
    assert not any(n.endswith(".lock") for n in names if n != MANIFEST_NAME)
    assert not any(n.startswith("recordings/") for n in names)
    assert not any(n.startswith("outputs/") for n in names)

    verified = service.verify_backup(dest)
    assert verified.ok


def test_include_recordings_and_outputs_skips_dest_zip(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    service.create_backup(
        ps,
        dest,
        BackupOptions(include_recordings=True, include_outputs=True),
    )
    with zipfile.ZipFile(dest) as zf:
        names = set(zf.namelist())
    assert "recordings/clip.wav" in names
    assert "outputs/old_run/manifest.json" in names
    assert "outputs/backups/workspace/ws.zip" not in names
    assert not any(n.endswith(".partial") for n in names)


def test_verify_rejects_zip_slip(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    service.create_backup(ps, dest)

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(dest, "r") as src, zipfile.ZipFile(evil, "w") as out:
        for info in src.infolist():
            out.writestr(info, src.read(info.filename))
        out.writestr("../escape.txt", b"nope")

    with pytest.raises(BackupError, match="zip-slip|unsafe|unexpected"):
        service.verify_backup(evil)


def test_dry_run_restore_does_not_write(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    service.create_backup(ps, dest)

    marker = ps.transcripts_dir / "demo.json"
    before = marker.read_bytes()
    (ps.transcripts_dir / "extra.txt").write_text("stay-for-dry-run", encoding="utf-8")

    result = service.restore_backup(ps, dest, safety=False, dry_run=True)
    assert result.dry_run
    assert result.ok
    assert marker.read_bytes() == before
    assert (ps.transcripts_dir / "extra.txt").is_file()
    assert any("mapped onto" in m for m in result.messages)
    assert any("archive counts:" in m for m in result.messages)


def test_create_refuses_existing_dest_without_force(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    service.create_backup(ps, dest)
    with pytest.raises(BackupError, match="already exists"):
        service.create_backup(ps, dest)
    service.create_backup(ps, dest, force=True)
    assert dest.is_file()


def test_restore_refuses_archive_under_transcripts(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    service = WorkspaceBackupService()
    good = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service.create_backup(ps, good)
    nested = ps.transcripts_dir / "ws.zip"
    nested.write_bytes(good.read_bytes())
    with pytest.raises(BackupError, match="replace root transcripts"):
        service.restore_backup(ps, nested, safety=False, dry_run=False)


def test_restore_allows_archive_under_workspace_backups(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    service = WorkspaceBackupService()
    archive = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service.create_backup(ps, archive, BackupOptions(include_outputs=True))
    result = service.restore_backup(ps, archive, safety=False, dry_run=True)
    assert result.ok


def test_create_refuses_insufficient_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    monkeypatch.setattr(workspace_backup_mod, "_free_disk_bytes", lambda _path: 1024)
    with pytest.raises(BackupError, match="insufficient free disk space"):
        WorkspaceBackupService().create_backup(ps, dest)


def test_restore_round_trip_replaces_and_clears_cache(tmp_path: Path) -> None:
    ps = _paths(tmp_path)
    _seed_workspace(ps)
    dest = ps.data_dir / "backups" / "workspace" / "ws.zip"
    service = WorkspaceBackupService()
    service.create_backup(ps, dest)

    (ps.transcripts_dir / "demo.json").write_text('{"mutated": true}\n', encoding="utf-8")
    (ps.transcripts_dir / "new_only.json").write_text("{}", encoding="utf-8")
    assert (ps.data_dir / "cache" / "audio_playback" / "x.bin").is_file()

    result = service.restore_backup(ps, dest, safety=True, dry_run=False)
    assert result.safety_archive is not None
    assert result.safety_archive.is_file()
    assert json.loads((ps.transcripts_dir / "demo.json").read_text(encoding="utf-8"))[
        "schema_version"
    ] == 1
    assert not (ps.transcripts_dir / "new_only.json").exists()
    assert not (ps.data_dir / "cache").exists()
    assert (ps.speaker_profiles_dir / "voice" / "samples" / "a.bin").read_bytes() == b"voice"
    assert (ps.config_dir / "config.json").is_file()
