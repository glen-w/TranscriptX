"""Performance contract for CorpusInventory (200+ transcripts, no segment parse)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.app.corpus_inventory.models import TranscriptRef
from transcriptx.app.corpus_inventory.service import CorpusInventory


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_corpus(tmp_path: Path, count: int = 220) -> list[TranscriptRef]:
    refs: list[TranscriptRef] = []
    for index in range(count):
        path = tmp_path / "transcripts" / f"tx_{index:03d}.json"
        _write_json(
            path,
            {
                "schema_version": 1,
                "metadata": {
                    "duration_seconds": 60 + index,
                    "speaker_count": 2,
                    "word_count": 100 + index,
                },
                "segments": [],
            },
        )
        refs.append(
            TranscriptRef(
                path=path.resolve(),
                base_name=path.stem,
                slug=path.stem,
                transcript_key=path.stem,
            )
        )
    return refs


def test_corpus_inventory_200_plus_zero_segment_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    refs = _make_corpus(tmp_path, 220)

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("load_segments must not run on the inventory list path")

    monkeypatch.setattr("transcriptx.io.transcript_loader.load_segments", _forbidden)
    monkeypatch.setattr("transcriptx.io.load_segments", _forbidden)

    inventory = CorpusInventory(load_corrections=lambda _p: None)
    rows, stats = inventory.list_rows_with_stats(refs)
    assert len(rows) == 220
    assert stats.rows_rebuilt == 220
    # One JSON read per transcript (metadata). Sidecars absent.
    assert stats.content_reads == 220
    assert stats.cache_hits == 0

    rows_warm, warm = inventory.list_rows_with_stats(refs)
    assert len(rows_warm) == 220
    assert warm.rows_rebuilt == 0
    assert warm.cache_hits == 220
    assert warm.content_reads == 0

    sidecar = refs[7].path.with_name(f"{refs[7].path.stem}.speaker_map.json")
    _write_json(
        sidecar,
        {"speaker_map": {"SPEAKER_00": "Ada", "SPEAKER_01": "Bob"}, "ignored_speakers": []},
    )
    rows_dirty, dirty = inventory.list_rows_with_stats(refs)
    assert dirty.rows_rebuilt == 1
    assert dirty.cache_hits == 219
    assert rows_dirty[7].speaker.status.value == "complete"
