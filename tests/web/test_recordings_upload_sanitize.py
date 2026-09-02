"""Recording upload basename sanitization."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.io.import_admission import AdmissionError
from transcriptx.web.services import recordings_service


class _FakeUpload:
    def __init__(self, name: str, data: bytes = b"RIFF") -> None:
        self.name = name
        self._data = data

    def read(self) -> bytes:
        return self._data


def test_save_uploaded_file_writes_single_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    imports = tmp_path / "imports"
    monkeypatch.setattr(recordings_service, "RECORDINGS_IMPORTS_DIR", imports)
    dest = recordings_service.RecordingsService.save_uploaded_file(
        _FakeUpload("meeting.wav")
    )
    assert dest == imports / "meeting.wav"
    assert dest.read_bytes() == b"RIFF"


def test_save_uploaded_file_strips_directory_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    imports = tmp_path / "imports"
    monkeypatch.setattr(recordings_service, "RECORDINGS_IMPORTS_DIR", imports)
    dest = recordings_service.RecordingsService.save_uploaded_file(
        _FakeUpload("nested/dir/clip.wav")
    )
    assert dest == imports / "clip.wav"
    assert dest.is_file()
    assert not (imports / "nested").exists()


def test_save_uploaded_file_rejects_parent_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    imports = tmp_path / "imports"
    monkeypatch.setattr(recordings_service, "RECORDINGS_IMPORTS_DIR", imports)
    with pytest.raises(AdmissionError, match="parent-directory"):
        recordings_service.RecordingsService.save_uploaded_file(
            _FakeUpload("../escape.wav")
        )
    assert list(tmp_path.rglob("escape.wav")) == []


def test_save_uploaded_file_overwrites_same_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    imports = tmp_path / "imports"
    monkeypatch.setattr(recordings_service, "RECORDINGS_IMPORTS_DIR", imports)
    first = recordings_service.RecordingsService.save_uploaded_file(
        _FakeUpload("same.wav", b"one")
    )
    second = recordings_service.RecordingsService.save_uploaded_file(
        _FakeUpload("same.wav", b"two")
    )
    assert first == second
    assert second.read_bytes() == b"two"
