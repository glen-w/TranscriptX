"""Tests for scripts/audio_preprocess.py and scripts/audio_merge.py helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    path = _REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def preprocess_mod():
    return _load("audio_preprocess_script", "scripts/audio_preprocess.py")


@pytest.fixture(scope="module")
def merge_mod():
    return _load("audio_merge_script", "scripts/audio_merge.py")


@pytest.mark.unit
def test_preprocess_assess_missing_file(preprocess_mod, tmp_path: Path) -> None:
    missing = tmp_path / "nope.wav"
    code = preprocess_mod.main(["assess", str(missing)])
    assert code == 1


@pytest.mark.unit
def test_preprocess_selected_requires_step(preprocess_mod, tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    code = preprocess_mod.main(["run", str(wav), "--mode", "selected"])
    assert code == 2


@pytest.mark.unit
def test_merge_requires_two_inputs(merge_mod, tmp_path: Path) -> None:
    only = tmp_path / "a.wav"
    only.write_bytes(b"x")
    code = merge_mod.main([str(only)])
    assert code == 2


@pytest.mark.unit
def test_merge_list_file(merge_mod, tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    listing = tmp_path / "paths.txt"
    listing.write_text(f"{a}\n# comment\n{b}\n", encoding="utf-8")

    from transcriptx.app.models.results import MergeResult

    captured: dict = {}

    def fake_run_merge(request, progress=None):
        captured["paths"] = list(request.file_paths)
        captured["backup"] = request.backup_wavs
        captured["delete_originals"] = request.delete_originals
        captured["apply_preprocessing"] = request.apply_preprocessing
        return MergeResult(
            success=True,
            output_path=tmp_path / "out.mp3",
            files_merged=2,
        )

    monkeypatch.setattr(merge_mod, "run_merge", fake_run_merge)
    code = merge_mod.main(
        ["--list", str(listing), "--no-backup", "-o", str(tmp_path / "out.mp3")]
    )
    assert code == 0
    assert captured["paths"] == [a.resolve(), b.resolve()]
    assert captured["backup"] is False
    assert captured["delete_originals"] is False
    assert captured["apply_preprocessing"] is False


@pytest.mark.unit
def test_merge_delete_originals_flag(merge_mod, tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    a.write_bytes(b"x")
    b.write_bytes(b"y")

    captured: dict = {}

    def fake_run_merge(request, progress=None):
        from transcriptx.app.models.results import MergeResult

        captured["delete_originals"] = request.delete_originals
        return MergeResult(success=True, files_merged=2)

    monkeypatch.setattr(merge_mod, "run_merge", fake_run_merge)
    code = merge_mod.main(
        [
            str(a),
            str(b),
            "--no-backup",
            "--delete-originals",
            "-o",
            str(tmp_path / "out.mp3"),
        ]
    )
    assert code == 0
    assert captured["delete_originals"] is True


@pytest.mark.unit
def test_merge_preprocess_flag(merge_mod, tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    a.write_bytes(b"x")
    b.write_bytes(b"y")

    captured: dict = {}

    def fake_run_merge(request, progress=None):
        from transcriptx.app.models.results import MergeResult

        captured["apply_preprocessing"] = request.apply_preprocessing
        return MergeResult(success=True, files_merged=2)

    monkeypatch.setattr(merge_mod, "run_merge", fake_run_merge)
    code = merge_mod.main(
        [str(a), str(b), "--no-backup", "--preprocess", "-o", str(tmp_path / "out.mp3")]
    )
    assert code == 0
    assert captured["apply_preprocessing"] is True
