"""Reader + v2 commit integration for authoritative generation files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_custom_qa.commit import (
    commit_llm_custom_qa_artifacts,
    generation_paths,
    read_active_generation_id,
)
from transcriptx.core.analysis.llm_custom_qa.structured_contracts import compute_structured_outcome
from transcriptx.core.analysis.llm_custom_qa.readers import (
    load_committed_custom_qa_payload,
    resolve_custom_qa_stem,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import SCHEMA_ID


def _minimal_v2_payload() -> dict:
    return {
        "schema_id": SCHEMA_ID,
        "module": "llm_custom_qa",
        "module_version": "2",
        "contract_version": "1",
        "questions_requested": [],
        "question_order": [],
        "questions_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "answers": [],
        "speaker_answers": [],
        "evidence_plan": {
            "routes": [],
            "routes_hash": "",
            "packs_available": [],
            "packs_missing": [],
            "packs_invalid": [],
            "packs_incompatible": [],
        },
        "effective_plan_summary": {
            "expanded_pack_ids": [],
            "catalog_version": "1",
            "speaker_keys": [],
            "speaker_limit": 0,
            "scheduler_version": "1",
            "fingerprint_refs": {},
        },
        "diagnostics": {
            "answers_over_limit": 0,
            "extra_or_duplicate_rows_dropped": 0,
            "response_incomplete_count": 0,
            "response_invalid_count": 0,
            "soft_quote_drops": 0,
            "input_truncated_overrides": 0,
            "absence_detector_hits": 0,
            "citations_total": 0,
            "cross_segment_citations_total": 0,
            "speakers_omitted_by_cap": [],
            "speaker_alias_collisions": 0,
            "llm_budget_exhausted_cells": 0,
            "alias_update_warnings": 0,
        },
        "input_coverage": {
            "version": 1,
            "input_chars_total": 0,
            "input_chars_used": 0,
            "input_coverage_ratio": None,
            "truncated": False,
            "segments_total": 0,
            "segments_used": 0,
            "segments_omitted_empty": 0,
            "segments_omitted_invalid": 0,
            "partial_final_segment": False,
            "transcript_fingerprint": None,
            "bounded_input_fingerprint": None,
        },
        "outcome": "empty_questions",
        "provenance": {
            "module": "llm_custom_qa",
            "schema_id": SCHEMA_ID,
            "module_version": "2",
            "contract_version": "1",
            "questions_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "question_order": [],
            "resolved_from": "explicit_empty",
            "empty_run": True,
            "cache_key": None,
            "run_execution_id": "run-deep-test",
        },
        "cache_key": None,
    }


@pytest.mark.unit
def test_reader_loads_v2_generation_named_artifact(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    global_dir = run_root / "data" / "global"
    global_dir.mkdir(parents=True)
    stem = global_dir / "demo_llm_custom_qa"
    payload = _minimal_v2_payload()
    gid = commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload=payload,
        markdown="# Custom Questions\n",
        run_execution_id="run-deep-test",
        force_protocol="generational",
    )
    json_gen, _, _ = generation_paths(stem, gid)
    assert json_gen.exists()
    assert read_active_generation_id(stem) == gid

    # Mark module success so reader accepts
    (run_root / "run_results.json").write_text(
        json.dumps({"modules_run": ["llm_custom_qa"], "modules_failed": []}),
        encoding="utf-8",
    )
    assert resolve_custom_qa_stem(run_root, base_name="demo") == stem
    loaded = load_committed_custom_qa_payload(run_root, base_name="demo")
    assert loaded is not None
    assert loaded["schema_id"] == SCHEMA_ID
    assert loaded["outcome"] == "empty_questions"


@pytest.mark.unit
def test_reader_resolves_module_scoped_global_layout(tmp_path: Path) -> None:
    """Production layout: run_root/llm_custom_qa/data/global/{base}_llm_custom_qa."""
    run_root = tmp_path / "run"
    global_dir = run_root / "llm_custom_qa" / "data" / "global"
    global_dir.mkdir(parents=True)
    stem = global_dir / "demo_llm_custom_qa"
    payload = _minimal_v2_payload()
    commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload=payload,
        markdown="# Custom Questions\n",
        run_execution_id="run-deep-test",
        force_protocol="generational",
    )
    (run_root / "run_results.json").write_text(
        json.dumps({"modules_run": ["llm_custom_qa"], "modules_failed": []}),
        encoding="utf-8",
    )
    assert resolve_custom_qa_stem(run_root) == stem
    loaded = load_committed_custom_qa_payload(run_root)
    assert loaded is not None
    assert loaded["schema_id"] == SCHEMA_ID


@pytest.mark.unit
def test_outcome_truth_table_no_scheduled_cells() -> None:
    assert (
        compute_structured_outcome(empty_questions=False, scheduled_statuses=[])
        == "no_scheduled_cells"
    )
    assert (
        compute_structured_outcome(
            empty_questions=False, scheduled_statuses=["answered", "unavailable"]
        )
        == "partial"
    )
