"""Tests for transcript file discovery."""

from pathlib import Path

from transcriptx.core.utils.file_discovery import (
    discover_all_transcript_paths,
    discover_managed_transcript_paths,
)


def test_discover_all_transcript_paths_ignores_speaker_map_sidecars(tmp_path: Path):
    """Speaker map sidecars should not appear in transcript dropdown sources."""
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()

    transcript_path = transcripts_dir / "interview.json"
    transcript_path.write_text("{}")

    speaker_map_path = transcripts_dir / "interview.speaker_map.json"
    speaker_map_path.write_text('{"speaker_map": {"SPEAKER_00": "Alice"}}')

    discovered = discover_all_transcript_paths(tmp_path)

    assert transcript_path.resolve() in discovered
    assert speaker_map_path.resolve() not in discovered


def test_discover_all_transcript_paths_ignores_metadata_originals_imports(
    tmp_path: Path,
):
    transcripts_dir = tmp_path / "transcripts"
    (transcripts_dir / "metadata").mkdir(parents=True)
    (transcripts_dir / "originals").mkdir(parents=True)
    (transcripts_dir / "imports").mkdir(parents=True)
    kept = transcripts_dir / "kept.json"
    kept.write_text("{}", encoding="utf-8")
    for path in (
        transcripts_dir / "metadata" / "meta.json",
        transcripts_dir / "originals" / "orig.json",
        transcripts_dir / "imports" / "imp.json",
    ):
        path.write_text("{}", encoding="utf-8")

    discovered = discover_all_transcript_paths(tmp_path)
    assert kept.resolve() in discovered
    assert not any(p.name in {"meta.json", "orig.json", "imp.json"} for p in discovered)


def test_discover_managed_transcript_paths_filters_invalid(tmp_path: Path, monkeypatch):
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir(parents=True)
    good = transcripts_dir / "good.json"
    bad = transcripts_dir / "bad.json"
    payload = '{"schema_version": 1, "source": {"type": "manual", "original_path": "good.json", "imported_at": "2020-01-01T00:00:00+00:00"}, "segments": []}'
    good.write_text(payload, encoding="utf-8")
    bad.write_text("{}", encoding="utf-8")

    class _Result:
        def __init__(self, ok: bool):
            self.ok = ok

    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda p: _Result(Path(p).name == "good.json"),
    )
    managed = discover_managed_transcript_paths(tmp_path)
    assert managed == [good.resolve()]
