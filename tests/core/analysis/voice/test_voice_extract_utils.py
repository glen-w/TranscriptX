from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.core.analysis.voice import extract as ve


def test_compute_segments_timing_hash_is_stable_and_changes_on_content() -> None:
    segs = [
        {"start": 0.0, "end": 1.0, "speaker": "Alice", "text": "a"},
        {"start": 1.0, "end": 2.0, "speaker": "Bob", "text": "b"},
    ]
    h1 = ve.compute_segments_timing_hash(segs, "tk")
    h2 = ve.compute_segments_timing_hash(segs, "tk")
    assert h1 == h2
    segs[1]["speaker"] = "Carol"
    h3 = ve.compute_segments_timing_hash(segs, "tk")
    assert h3 != h1


def test_compute_voice_config_hash_reflects_voice_knobs() -> None:
    cfg1 = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(sample_rate=16000, vad_mode=1))
    )
    cfg2 = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(sample_rate=48000, vad_mode=1))
    )
    assert ve.compute_voice_config_hash(cfg1) != ve.compute_voice_config_hash(cfg2)


def test_copy_if_needed_creates_destination_once(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    dst = tmp_path / "nested" / "b.txt"
    src.write_text("hello", encoding="utf-8")
    ve._copy_if_needed(src, dst)
    assert dst.exists()


def test_copy_if_needed_does_not_replace_existing_destination(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    dst = tmp_path / "nested" / "b.txt"
    src.write_text("hello", encoding="utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("existing", encoding="utf-8")
    ve._copy_if_needed(src, dst)
    assert dst.read_text(encoding="utf-8") == "existing"
