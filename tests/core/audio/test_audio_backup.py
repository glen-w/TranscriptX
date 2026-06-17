"""Unit tests for ``core.audio.backup`` (pure file backup helpers).

Offline and deterministic: no ffmpeg/audio decoding. The module performs only
filesystem copies, so the destination (``PATHS.wav_backup_dir``) and the
upload-guard root (``RECORDINGS_IMPORTS_DIR``) are redirected to ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.audio import backup as backup_mod


@pytest.fixture
def backup_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect storage + imports roots into tmp_path.

    Returns (storage_dir, imports_dir). ``storage_dir`` is intentionally not
    pre-created so tests also exercise the ``mkdir`` branch.
    """
    storage_dir = tmp_path / "wav_backups"
    imports_dir = tmp_path / "recordings" / "imports"
    imports_dir.mkdir(parents=True)

    monkeypatch.setattr(
        backup_mod, "PATHS", SimpleNamespace(wav_backup_dir=storage_dir)
    )
    monkeypatch.setattr(backup_mod, "RECORDINGS_IMPORTS_DIR", imports_dir)
    return storage_dir, imports_dir


def _make_audio(path: Path, content: bytes = b"RIFFfake-wav") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.mark.unit
class TestIsUnderImports:
    def test_true_when_under_imports(self, backup_dirs):
        _, imports_dir = backup_dirs
        src = _make_audio(imports_dir / "clip.wav")
        assert backup_mod._is_under_imports(src) is True

    def test_false_when_outside_imports(self, backup_dirs, tmp_path):
        src = _make_audio(tmp_path / "elsewhere" / "clip.wav")
        assert backup_mod._is_under_imports(src) is False


@pytest.mark.unit
class TestBackupAudioFilesToStorage:
    def test_empty_input_returns_empty(self, backup_dirs):
        assert backup_mod.backup_audio_files_to_storage([]) == []

    def test_keeps_original_stem_without_base_name(self, backup_dirs, tmp_path):
        storage_dir, _ = backup_dirs
        src = _make_audio(tmp_path / "src" / "meeting.wav")

        result = backup_mod.backup_audio_files_to_storage([src], delete_original=False)

        assert result == [storage_dir / "meeting.wav"]
        assert (storage_dir / "meeting.wav").exists()
        # storage dir was created on demand
        assert storage_dir.is_dir()

    def test_base_name_produces_numbered_backups(self, backup_dirs, tmp_path):
        storage_dir, _ = backup_dirs
        a = _make_audio(tmp_path / "a.wav")
        b = _make_audio(tmp_path / "b.mp3")

        result = backup_mod.backup_audio_files_to_storage(
            [a, b], base_name="260108_merged", delete_original=False
        )

        assert result == [
            storage_dir / "260108_merged_1.wav",
            storage_dir / "260108_merged_2.mp3",
        ]
        assert all(p.exists() for p in result)

    def test_missing_source_is_skipped(self, backup_dirs, tmp_path):
        storage_dir, _ = backup_dirs
        present = _make_audio(tmp_path / "present.wav")
        missing = tmp_path / "missing.wav"

        result = backup_mod.backup_audio_files_to_storage(
            [missing, present], delete_original=False
        )

        assert result == [storage_dir / "present.wav"]

    def test_name_conflict_gets_counter_suffix(self, backup_dirs, tmp_path):
        storage_dir, _ = backup_dirs
        storage_dir.mkdir(parents=True)
        # Pre-existing backup with the same target name forces a counter suffix.
        (storage_dir / "clip.wav").write_bytes(b"old")
        src = _make_audio(tmp_path / "clip.wav", content=b"new")

        result = backup_mod.backup_audio_files_to_storage([src], delete_original=False)

        assert result == [storage_dir / "clip_1.wav"]
        assert (storage_dir / "clip.wav").read_bytes() == b"old"
        assert (storage_dir / "clip_1.wav").read_bytes() == b"new"

    def test_deletes_original_under_imports(self, backup_dirs):
        storage_dir, imports_dir = backup_dirs
        src = _make_audio(imports_dir / "upload.wav")

        result = backup_mod.backup_audio_files_to_storage([src], delete_original=True)

        assert result == [storage_dir / "upload.wav"]
        assert not src.exists()

    def test_keeps_original_outside_imports_even_when_delete_requested(
        self, backup_dirs, tmp_path
    ):
        storage_dir, _ = backup_dirs
        src = _make_audio(tmp_path / "recordings" / "keep.wav")

        result = backup_mod.backup_audio_files_to_storage([src], delete_original=True)

        assert result == [storage_dir / "keep.wav"]
        # Outside the imports dir the original must never be deleted.
        assert src.exists()

    def test_delete_original_false_keeps_upload(self, backup_dirs):
        _, imports_dir = backup_dirs
        src = _make_audio(imports_dir / "upload.wav")

        backup_mod.backup_audio_files_to_storage([src], delete_original=False)

        assert src.exists()

    def test_copy_failure_is_isolated_per_file(
        self, backup_dirs, tmp_path, monkeypatch
    ):
        storage_dir, _ = backup_dirs
        good = _make_audio(tmp_path / "good.wav")
        bad = _make_audio(tmp_path / "bad.wav")

        real_copy = backup_mod.shutil.copy2

        def flaky_copy(src, dst, *args, **kwargs):
            if Path(src).name == "bad.wav":
                raise OSError("disk full")
            return real_copy(src, dst, *args, **kwargs)

        monkeypatch.setattr(backup_mod.shutil, "copy2", flaky_copy)

        result = backup_mod.backup_audio_files_to_storage(
            [bad, good], delete_original=False
        )

        # Failure on one file does not abort the batch.
        assert result == [storage_dir / "good.wav"]
