"""Unit tests for topic_shift enrichment resolve + generational store."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.llm_generational_store import (
    begin_generation,
    build_inventory,
    commit_and_activate,
    load_active_artifact,
    read_active,
)
from transcriptx.core.analysis.llm_support.model_selection import (
    LlmModelSelection,
    bind_llm_model_selection,
    reset_llm_model_selection,
)
from transcriptx.core.analysis.topic_shift.enrichment import (
    maybe_run_topic_shift_enrichment,
)
from transcriptx.core.analysis.topic_shift.enrichment_resolve import (
    resolve_topic_shift_enrichment_model,
)
from transcriptx.core.analysis.topic_shift.visibility import (
    resolve_topic_shift_visibility,
)
from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL


def test_resolve_never_falls_through_to_default_ollama_model() -> None:
    llm_cfg = SimpleNamespace(model=None, model_selection=None)
    resolved = resolve_topic_shift_enrichment_model(llm_cfg)
    assert resolved.status == "skipped"
    assert resolved.model is None
    assert resolved.skip_reason == "no_configured_model"
    assert resolved.model != DEFAULT_OLLAMA_MODEL


def test_resolve_uses_bound_per_module_selection() -> None:
    llm_cfg = SimpleNamespace(model=None, model_selection=None)
    token = bind_llm_model_selection(
        LlmModelSelection(
            mode="per_module",
            module_models={"topic_shift": "my-topic-model:7b"},
        )
    )
    try:
        resolved = resolve_topic_shift_enrichment_model(
            llm_cfg,
            installed_models_provider=lambda: ["my-topic-model:7b"],
        )
        assert resolved.status == "ok"
        assert resolved.model == "my-topic-model:7b"
        assert resolved.source == "request"
    finally:
        reset_llm_model_selection(token)


def test_llm_generational_store_rejects_empty_digest(tmp_path: Path) -> None:
    staged = begin_generation(tmp_path, store_dirname=".test_store")
    with pytest.raises(ValueError, match="empty digest"):
        build_inventory(staged, ["missing.json"], reject_empty=True)


def test_llm_generational_store_commit_activate(tmp_path: Path) -> None:
    staged = begin_generation(
        tmp_path,
        store_dirname=".test_store",
        extra_meta={"deterministic_generation_id": "abc"},
    )
    staged.write_json("payload.json", {"ok": True})
    commit_and_activate(staged, rel_paths=["payload.json"], status="skipped")
    active = read_active(tmp_path / ".test_store")
    assert active is not None
    assert active["generation_id"] == staged.generation_id
    loaded = load_active_artifact(tmp_path / ".test_store", "payload.json")
    assert loaded == {"ok": True}


def test_enrichment_skipped_when_llm_disabled(tmp_path: Path) -> None:
    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    spans = {
        "deterministic_generation_id": "det1",
        "analytical_status": "no_shift_detected",
        "schema_version": "topic_shift_spans_v1",
        "coverage_spans": [
            {"span_id": "s1", "index": 0, "label": "Whole conversation"},
        ],
    }
    payload = maybe_run_topic_shift_enrichment(
        module_output_dir=module_dir,
        spans_envelope=spans,
        llm_cfg=SimpleNamespace(
            enabled=False, model="x", model_selection=None, base_url=None
        ),
        llm_enabled=False,
    )
    assert payload["outcome"] == "skipped"
    assert payload["skip_reason"] == "llm_disabled"
    assert payload["ui_mode"] == "overall_summary"
    mirror = module_dir / "data" / "global" / "topic_shift.enrichment.json"
    assert mirror.is_file()


def test_resolve_skips_when_model_not_installed() -> None:
    llm_cfg = SimpleNamespace(model="missing:7b", model_selection=None, base_url=None)
    resolved = resolve_topic_shift_enrichment_model(
        llm_cfg,
        installed_models_provider=lambda: ["other:7b"],
    )
    assert resolved.status == "skipped"
    assert resolved.skip_reason == "model_not_installed"
    assert resolved.model == "missing:7b"


def test_resolve_skips_when_ollama_unreachable() -> None:
    llm_cfg = SimpleNamespace(model="x:7b", model_selection=None, base_url=None)

    def _boom() -> list[str]:
        raise RuntimeError("down")

    resolved = resolve_topic_shift_enrichment_model(
        llm_cfg, installed_models_provider=_boom
    )
    assert resolved.status == "skipped"
    assert resolved.skip_reason == "ollama_unreachable"


def test_visibility_suppresses_failed(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "topic_shift" / "data" / "global").mkdir(parents=True)
    (
        run_root / "topic_shift" / "data" / "global" / "topic_shift.spans.json"
    ).write_text("{}", encoding="utf-8")
    run_results = {
        "run_id": "r1",
        "modules_enabled": ["topic_shift"],
        "modules_run": [],
        "modules_failed": ["topic_shift"],
        "modules_skipped": [],
        "module_outcomes": [
            {"module_id": "topic_shift", "status": "failed", "error_message": "boom"},
        ],
    }
    assert (
        resolve_topic_shift_visibility(run_root, run_results=run_results)
        == "suppress_failed"
    )


def test_enrichment_envelope_rejects_duplicate_span_ids() -> None:
    from pydantic import ValidationError

    from transcriptx.core.analysis.topic_shift.schemas import (
        validate_enrichment_payload,
    )

    payload = {
        "schema_version": "transcriptx.topic_shift_enrichment.v1",
        "prompt_version": "topic_shift_enrichment_prompt_v1",
        "outcome": "success",
        "skip_reason": None,
        "deterministic_generation_id": "g1",
        "deterministic_digest": "d" * 64,
        "model": "m",
        "selection_source": "config",
        "entries": [
            {
                "span_id": "s1",
                "title": "A",
                "summary": None,
                "key_points": [],
                "title_source": "llm",
                "error_category": None,
            },
            {
                "span_id": "s1",
                "title": "B",
                "summary": None,
                "key_points": [],
                "title_source": "llm",
                "error_category": None,
            },
        ],
        "overall_summary": None,
        "ui_mode": "chapter_titles",
    }
    with pytest.raises(ValidationError, match="duplicate"):
        validate_enrichment_payload(payload)


def test_is_usable_chapter_title_rejects_segment_echo() -> None:
    from transcriptx.core.analysis.topic_shift.titles import is_usable_chapter_title

    assert is_usable_chapter_title("Budget review")
    assert not is_usable_chapter_title("Segment 1")
    assert not is_usable_chapter_title("Segment 2 · 01:00–02:00")
    assert not is_usable_chapter_title("Chapter 3")
    assert not is_usable_chapter_title(
        "Segment 1 · 00:00–01:00",
        span_label="Segment 1 · 00:00–01:00",
    )
    assert not is_usable_chapter_title("")


def test_try_generate_titles_rejects_generic_and_keeps_summary(monkeypatch) -> None:
    from transcriptx.core.analysis.topic_shift import enrichment as enrich_mod

    class _Client:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            return json.dumps(
                {
                    "entries": [
                        {
                            "span_id": "s1",
                            "title": "Segment 1 · 00:00–01:00",
                            "summary": "Discussed hiring plan.",
                            "key_points": ["hiring"],
                        },
                        {
                            "span_id": "s2",
                            "title": "Q3 roadmap",
                            "summary": "Prioritized features.",
                            "key_points": [],
                        },
                    ]
                }
            )

    monkeypatch.setattr(
        enrich_mod,
        "OllamaClient",
        _Client,
        raising=False,
    )
    # Patch inside the import path used by _try_generate_titles
    import transcriptx.core.llm.ollama_client as oc

    monkeypatch.setattr(oc, "OllamaClient", _Client)
    monkeypatch.setattr(oc, "resolve_ollama_base_url", lambda x: x)

    outcome, entries, _ = enrich_mod._try_generate_titles(
        model="m:1",
        spans=[
            {
                "span_id": "s1",
                "label": "Segment 1 · 00:00–01:00",
                "keyword_hints": ["hiring"],
                "text_excerpt": "We need to hire two engineers.",
            },
            {
                "span_id": "s2",
                "label": "Segment 2 · 01:00–02:00",
                "keyword_hints": ["roadmap"],
                "text_excerpt": "Next quarter focus is the roadmap.",
            },
        ],
        llm_cfg=SimpleNamespace(
            base_url="http://localhost:11434",
            request_timeout=30,
            seed=1,
            availability_timeout=1,
        ),
    )
    assert outcome == "partial"
    assert entries[0]["title"] is None
    assert entries[0]["summary"] == "Discussed hiring plan."
    assert entries[0]["error_category"] == "generic_title"
    assert entries[1]["title"] == "Q3 roadmap"


def test_malformed_enrichment_does_not_break_commit(
    tmp_path: Path, monkeypatch
) -> None:
    from transcriptx.core.analysis.topic_shift import enrichment as enrich_mod

    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    spans = {
        "deterministic_generation_id": "det1",
        "analytical_status": "success",
        "schema_version": "transcriptx.topic_shift_result.v1",
        "semantics_version": "topic_shift_semantics_v1",
        "backend": "tfidf",
        "coverage_spans": [
            {"span_id": "s1", "index": 0, "label": "Opening"},
            {"span_id": "s2", "index": 1, "label": "Next"},
        ],
    }

    def _bad_titles(*, model, spans, llm_cfg):
        return (
            "success",
            [
                {
                    "span_id": "s1",
                    "title": "One",
                    "summary": None,
                    "key_points": [],
                    "title_source": "llm",
                    "error_category": None,
                },
                {
                    "span_id": "s1",
                    "title": "Dup",
                    "summary": None,
                    "key_points": [],
                    "title_source": "llm",
                    "error_category": None,
                },
            ],
            None,
        )

    monkeypatch.setattr(enrich_mod, "_try_generate_titles", _bad_titles)
    monkeypatch.setattr(
        enrich_mod,
        "resolve_topic_shift_enrichment_model",
        lambda *a, **k: SimpleNamespace(
            status="ok", model="m:1", source="config", skip_reason=None
        ),
    )
    det_before = spans["coverage_spans"]
    payload = maybe_run_topic_shift_enrichment(
        module_output_dir=module_dir,
        spans_envelope=spans,
        llm_cfg=SimpleNamespace(enabled=True, model="m:1", model_selection=None),
        llm_enabled=True,
    )
    assert payload["outcome"] == "skipped"
    assert payload["skip_reason"] == "malformed_enrichment"
    assert spans["coverage_spans"] is det_before
