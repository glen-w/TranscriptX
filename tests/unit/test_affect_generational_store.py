"""Generational artifact store tests (current_complete vs latest_attempt)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.emotion_family.generational_store import (
    INDEX_FILENAME,
    ArtifactGenerationIndex,
    load_current_complete_rows,
    load_index,
    persist_generation,
    persist_generation_from_results,
)


@pytest.mark.unit
def test_complete_usable_generation_becomes_current(tmp_path):
    persist_generation(
        tmp_path,
        module_id="emotion",
        generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        run_status="complete",
        usable_output=True,
        canonical_rows=[{"segment_id": "s1", "coverage": 0.5}],
    )
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation == "0120a4f9196a5f9eb9f523f31f914da7"
    assert index.latest_attempt_generation == "0120a4f9196a5f9eb9f523f31f914da7"
    rows = load_current_complete_rows(tmp_path)
    assert rows == [{"segment_id": "s1", "coverage": 0.5}]


@pytest.mark.unit
def test_failed_attempt_preserves_prior_complete(tmp_path):
    persist_generation(
        tmp_path,
        module_id="emotion",
        generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        run_status="complete",
        usable_output=True,
        canonical_rows=[{"segment_id": "s1"}],
    )
    persist_generation(
        tmp_path,
        module_id="emotion",
        generation_id="e1c80488853d86ab9d6decfe30d8930f",
        run_status="failed",
        usable_output=False,
        canonical_rows=[],
    )
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation == "0120a4f9196a5f9eb9f523f31f914da7"
    assert index.latest_attempt_generation == "e1c80488853d86ab9d6decfe30d8930f"
    # Prior complete rows remain readable.
    assert load_current_complete_rows(tmp_path) == [{"segment_id": "s1"}]
    # Failed attempt remains inspectable in history.
    assert any(
        e["artifact_generation_id"] == "e1c80488853d86ab9d6decfe30d8930f"
        and e["run_status"] == "failed"
        for e in index.attempt_history
    )


@pytest.mark.unit
def test_complete_but_not_usable_does_not_become_current(tmp_path):
    persist_generation(
        tmp_path,
        module_id="contextual_emotion",
        generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        run_status="complete",
        usable_output=False,  # e.g. zero scored segments
        canonical_rows=[],
    )
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation is None
    assert index.latest_attempt_generation == "0120a4f9196a5f9eb9f523f31f914da7"
    assert load_current_complete_rows(tmp_path) is None


@pytest.mark.unit
def test_persist_generation_from_results_adapter(tmp_path):
    results = {
        "artifact_generation_id": "6e5c7ab65dcf8d219e29cb0991b2632d",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "compatibility_fingerprint": "abc",
        "canonical_rows": [
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "h1",
            },
            {
                "segment_id": "s2",
                "evaluation_state": "scored",
                "scored_text_hash": "h2",
            },
        ],
    }
    output_service = SimpleNamespace(
        get_output_structure=lambda: SimpleNamespace(module_dir=tmp_path)
    )
    gen_dir = persist_generation_from_results(results, output_service, "emotion")
    assert gen_dir is not None
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.module_id == "emotion"
    assert index.current_complete_generation == "6e5c7ab65dcf8d219e29cb0991b2632d"
    entry = index.attempt_history[-1]
    assert entry["compatibility_fingerprint"] == "abc"
    assert entry["segments_scored"] == 2


@pytest.mark.unit
def test_index_roundtrip_and_history_bound(tmp_path):
    index = ArtifactGenerationIndex(module_id="m")
    data = index.to_dict()
    restored = ArtifactGenerationIndex.from_dict(json.loads(json.dumps(data)))
    assert restored.module_id == "m"
    assert restored.current_complete_generation is None
