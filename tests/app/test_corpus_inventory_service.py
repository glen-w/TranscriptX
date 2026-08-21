"""CorpusInventory I/O, invalidation, and best-effort discovery tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.app.corpus_inventory.models import (
    AnalysisStatus,
    CorrectionsStatus,
    FieldIntegrity,
    SpeakerIdStatus,
    TranscriptRef,
)
from transcriptx.app.corpus_inventory.service import CorpusInventory


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _transcript(
    tmp_path: Path,
    name: str,
    *,
    duration: float = 120.0,
    speakers: int = 2,
    words: int = 500,
) -> Path:
    path = tmp_path / "transcripts" / f"{name}.json"
    _write_json(
        path,
        {
            "schema_version": 1,
            "metadata": {
                "duration_seconds": duration,
                "speaker_count": speakers,
                "word_count": words,
            },
            "segments": [],
        },
    )
    return path


def _ref(path: Path, slug: str | None = None) -> TranscriptRef:
    return TranscriptRef(
        path=path.resolve(),
        base_name=path.stem,
        slug=slug or path.stem,
        transcript_key=path.stem,
    )


def test_list_rows_reads_metadata_without_segments(tmp_path: Path) -> None:
    path = _transcript(tmp_path, "alice", duration=4920, speakers=3, words=10430)
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    rows = inventory.list_rows([_ref(path)])
    assert len(rows) == 1
    row = rows[0]
    assert row.duration_seconds == 4920
    assert row.speaker_count == 3
    assert row.word_count == 10430
    assert row.analysis.status is AnalysisStatus.UNANALYSED
    assert row.speaker.status is SpeakerIdStatus.NONE
    assert row.corrections.status is CorrectionsStatus.NEVER_STARTED


def test_corrupt_transcript_still_emits_row(tmp_path: Path) -> None:
    good = _transcript(tmp_path, "good")
    bad = tmp_path / "transcripts" / "bad.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    rows = inventory.list_rows([_ref(good), _ref(bad)])
    assert len(rows) == 2
    by_name = {row.title: row for row in rows}
    assert by_name["good"].listing_integrity is FieldIntegrity.OK
    assert by_name["bad"].listing_integrity is FieldIntegrity.MALFORMED
    assert by_name["bad"].duration_seconds is None


def test_speaker_map_changes_row_not_last_analysed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _transcript(tmp_path, "meet", speakers=2)
    sidecar = path.with_name("meet.speaker_map.json")
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    refs = [_ref(path)]
    first = inventory.list_rows(refs)[0]
    analysed_before = first.analysis.last_analysed_at

    _write_json(
        sidecar,
        {"speaker_map": {"SPEAKER_00": "Ada", "SPEAKER_01": "Bob"}, "ignored_speakers": []},
    )
    inventory.reset_counters()
    second = inventory.list_rows(refs)[0]
    assert second.speaker.status is SpeakerIdStatus.COMPLETE
    assert second.analysis.last_analysed_at == analysed_before
    assert second.last_activity_at is not None
    assert inventory.rows_rebuilt == 1


def test_new_run_updates_analysis_and_last_analysed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _transcript(tmp_path, "runme")
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.OUTPUTS_DIR", outputs
    )
    monkeypatch.setattr(
        "transcriptx.app.corpus_inventory.service.output_root_for",
        lambda ref: outputs / (ref.slug or ref.path.stem),
    )
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    refs = [_ref(path, slug="runme")]
    first = inventory.list_rows(refs)[0]
    assert first.analysis.status is AnalysisStatus.UNANALYSED
    assert first.analysis.last_analysed_at is None

    run_dir = outputs / "runme" / "run-1"
    _write_json(
        run_dir / "run_results.json",
        {
            "modules_enabled": ["sentiment", "topics"],
            "modules_run": ["sentiment"],
            "modules_failed": [],
            "modules_skipped": [
                {
                    "module": "topics",
                    "execution_status": "skipped",
                    "reason": "policy",
                }
            ],
        },
    )
    inventory.reset_counters()
    second = inventory.list_rows(refs)[0]
    assert second.analysis.status is AnalysisStatus.COMPLETED
    assert second.analysis.modules_succeeded == 1
    assert second.analysis.modules_eligible == 1
    assert second.analysis.last_analysed_at is not None
    assert second.last_activity_at == second.analysis.last_analysed_at
    assert inventory.rows_rebuilt == 1


def test_corrections_change_does_not_set_last_analysed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _transcript(tmp_path, "corr")
    session_file = tmp_path / "corrections" / "corr" / "session.json"
    monkeypatch.setattr(
        "transcriptx.app.corpus_inventory.service._legacy_corrections_session_path",
        lambda _p: session_file,
    )
    sessions: dict[str, dict] = {}

    def load_corr(p: Path):
        return sessions.get(str(p.resolve()))

    inventory = CorpusInventory(load_corrections=load_corr)
    refs = [_ref(path)]
    first = inventory.list_rows(refs)[0]
    assert first.corrections.status is CorrectionsStatus.NEVER_STARTED

    payload = {
        "current_generation_id": 1,
        "updated_at": "2026-08-20T12:00:00Z",
        "candidates": [{"generation_id": 1, "review_status": "pending"}],
    }
    sessions[str(path.resolve())] = payload
    _write_json(session_file, payload)
    inventory.reset_counters()
    second = inventory.list_rows(refs)[0]
    assert second.corrections.status is CorrectionsStatus.PENDING
    assert second.corrections.pending_count == 1
    assert second.analysis.last_analysed_at is None
    assert second.last_activity_at is not None
    assert inventory.rows_rebuilt == 1


def test_unrelated_sidecar_does_not_rebuild_other_row(tmp_path: Path) -> None:
    a = _transcript(tmp_path, "alpha")
    b = _transcript(tmp_path, "beta")
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    refs = [_ref(a), _ref(b)]
    inventory.list_rows(refs)
    inventory.reset_counters()
    inventory.list_rows(refs)
    assert inventory.rows_rebuilt == 0
    assert inventory.cache_hits == 2

    _write_json(
        a.with_name("alpha.speaker_map.json"),
        {"speaker_map": {"SPEAKER_00": "Ada"}, "ignored_speakers": []},
    )
    inventory.reset_counters()
    inventory.list_rows(refs)
    assert inventory.rows_rebuilt == 1
    assert inventory.cache_hits == 1


def test_malformed_speaker_sidecar_still_lists(tmp_path: Path) -> None:
    path = _transcript(tmp_path, "weird")
    path.with_name("weird.speaker_map.json").write_text("[]", encoding="utf-8")
    inventory = CorpusInventory(load_corrections=lambda _p: None)
    row = inventory.list_rows([_ref(path)])[0]
    assert row.speaker.status is SpeakerIdStatus.UNKNOWN
    assert row.speaker.integrity is FieldIntegrity.MALFORMED
    assert row.title == "weird"
