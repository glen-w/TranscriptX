from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.io.import_managed import workflow as mod


class _FakeLock:
    def __init__(self, _path, timeout=30, acquired=True):
        self.acquired = acquired

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_roots(monkeypatch: pytest.MonkeyPatch, root: Path) -> tuple[Path, Path]:
    out = root / "transcripts"
    originals = out / "originals"
    out.mkdir(parents=True, exist_ok=True)
    originals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mod, "DIARISED_TRANSCRIPTS_DIR", out)
    monkeypatch.setattr(mod, "TRANSCRIPTS_ORIGINALS_DIR", originals)
    return out, originals


def test_extract_retry_source_relpath_validates_and_returns(tmp_path: Path) -> None:
    output = tmp_path / "out"
    archive = output / "originals" / "a.srt"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("x", encoding="utf-8")
    doc = output / "a.json"
    doc.write_text(
        json.dumps({"source": {"original_path": "originals/a.srt"}}), encoding="utf-8"
    )

    rel = mod._extract_retry_source_original_relpath(json_path=doc, output_dir=output)
    assert rel == "originals/a.srt"


def test_extract_retry_source_relpath_rejects_unsafe(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir(parents=True, exist_ok=True)
    doc = output / "a.json"
    doc.write_text(
        json.dumps({"source": {"original_path": "../evil.srt"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="safe relative path"):
        mod._extract_retry_source_original_relpath(json_path=doc, output_dir=output)


def test_workflow_missing_staging_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mod.run_managed_import_workflow(tmp_path / "missing.srt")


def test_workflow_lock_not_acquired_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out, _ = _patch_roots(monkeypatch, tmp_path)
    staging = tmp_path / "in.srt"
    staging.write_text("x", encoding="utf-8")

    class _NoLock(_FakeLock):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.acquired = False

    monkeypatch.setattr(mod, "FileLock", _NoLock)
    with pytest.raises(RuntimeError, match="Could not acquire import lock"):
        mod.run_managed_import_workflow(staging)


def test_existing_target_with_sidecar_and_no_overwrite_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out, _ = _patch_roots(monkeypatch, tmp_path)
    staging = tmp_path / "meeting.srt"
    staging.write_text("x", encoding="utf-8")
    (out / "meeting.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(mod, "FileLock", _FakeLock)
    monkeypatch.setattr(
        mod,
        "sidecar_path_for_transcript",
        lambda _p: out / "metadata" / "meeting.meta.json",
    )
    (out / "metadata").mkdir(parents=True, exist_ok=True)
    (out / "metadata" / "meeting.meta.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="sidecar exists"):
        mod.run_managed_import_workflow(staging, overwrite=False)


def test_retry_existing_json_writes_sidecar_without_reimport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out, _ = _patch_roots(monkeypatch, tmp_path)
    staging = tmp_path / "meeting.srt"
    staging.write_text("x", encoding="utf-8")
    target = out / "meeting.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"source": {"original_path": "originals/meeting.srt"}}),
        encoding="utf-8",
    )
    (out / "originals" / "meeting.srt").write_text("archive", encoding="utf-8")

    monkeypatch.setattr(mod, "FileLock", _FakeLock)
    monkeypatch.setattr(
        mod,
        "sidecar_path_for_transcript",
        lambda _p: out / "metadata" / "meeting.meta.json",
    )
    monkeypatch.setattr(
        mod,
        "write_initial_sidecar",
        lambda *_a, **_k: out / "metadata" / "meeting.meta.json",
    )
    monkeypatch.setattr(
        mod,
        "validate_managed_transcript",
        lambda _p: SimpleNamespace(ok=True, message="ok"),
    )

    result = mod.run_managed_import_workflow(
        staging, overwrite=False, delete_staging_on_success=True
    )
    assert result.adapter_source_id == "existing"
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert not staging.exists()


def test_import_failure_does_not_write_json_or_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out, originals = _patch_roots(monkeypatch, tmp_path)
    staging = tmp_path / "meeting.srt"
    staging.write_text("x", encoding="utf-8")

    monkeypatch.setattr(mod, "FileLock", _FakeLock)
    monkeypatch.setattr(mod, "build_default_registry", lambda: object())
    monkeypatch.setattr(
        mod,
        "run_import_orchestration",
        lambda **_k: (_ for _ in ()).throw(ValueError("parse failed")),
    )

    with pytest.raises(ValueError, match="parse failed"):
        mod.run_managed_import_workflow(staging, overwrite=False)

    assert not (out / "meeting.json").exists()
    assert not (out / "metadata").exists()
    archived = list(originals.glob("meeting*"))
    assert len(archived) == 1
