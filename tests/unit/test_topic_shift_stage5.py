"""Stage 5 acceptance: store crash-injection, byte identity, schemas, aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.topic_shift.aggregation import aggregate_topic_shift
from transcriptx.core.analysis.topic_shift.analyze import run_topic_shift_analysis
from transcriptx.core.analysis.topic_shift.enrichment import (
    maybe_run_topic_shift_enrichment,
)
from transcriptx.core.analysis.topic_shift.schemas import (
    EventsEnvelopeModel,
    SpansEnvelopeModel,
    StatsEnvelopeModel,
)
from transcriptx.core.analysis.topic_shift.store import (
    begin_attempt,
    commit_and_activate,
    content_digest,
    record_failed_attempt,
    resolve_active_generation,
)
from transcriptx.core.analysis.topic_shift.visibility import (
    resolve_topic_shift_visibility,
    suppress_topic_shift_surface_artifacts,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.output.output_service import OutputService


def _two_topic_segments(n: int = 24) -> list[dict]:
    segs = []
    for i in range(n):
        if i < n // 2:
            text = (
                "Budget planning finance cost revenue profit margin "
                "accounting ledger fiscal quarter "
            ) * 3
        else:
            text = (
                "Sports match football soccer goal stadium fan "
                "tournament league championship athlete "
            ) * 3
        segs.append(
            {
                "index": i,
                "speaker": "A" if i % 2 == 0 else "B",
                "text": text.strip(),
                "start": float(i * 5),
                "end": float(i * 5 + 4.5),
            }
        )
    return segs


def test_crash_injection_keeps_prior_complete(tmp_path: Path) -> None:
    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    staged1 = begin_attempt(module_dir)
    for name, payload in (
        ("topic_shift.spans.json", {"ok": 1}),
        ("topic_shift.events.json", {"ok": 1}),
        ("topic_shift.stats.json", {"ok": 1}),
    ):
        staged1.write_json(name, payload)
    commit_and_activate(staged1)
    active1 = resolve_active_generation(module_dir)
    assert active1 is not None
    assert active1.name == staged1.generation_id

    staged2 = begin_attempt(module_dir)
    staged2.write_json("topic_shift.spans.json", {"partial": True})
    # Simulate crash before COMMIT
    record_failed_attempt(module_dir, staged2.generation_id)
    active2 = resolve_active_generation(module_dir)
    # Failed latest attempt suppresses ACTIVE for platform visibility
    assert active2 is None
    # Prior generation still on disk with COMMIT
    assert (staged1.directory / "COMMIT.json").is_file()
    assert not (staged2.directory / "COMMIT.json").is_file()


def test_incomplete_generation_without_commit_invisible(tmp_path: Path) -> None:
    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    staged = begin_attempt(module_dir)
    staged.write_json("topic_shift.spans.json", {"x": 1})
    staged.write_json("topic_shift.events.json", {"x": 1})
    staged.write_json("topic_shift.stats.json", {"x": 1})
    # No commit_and_activate
    assert resolve_active_generation(module_dir) is None


def test_commit_rejects_empty_inventory(tmp_path: Path) -> None:
    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    staged = begin_attempt(module_dir)
    # Write file but clear inventory digest to simulate corruption
    path = staged.directory / "topic_shift.spans.json"
    path.write_text("{}", encoding="utf-8")
    staged.inventory["topic_shift.spans.json"] = ""
    staged.write_json("topic_shift.events.json", {})
    staged.write_json("topic_shift.stats.json", {})
    with pytest.raises(RuntimeError, match="empty digest"):
        commit_and_activate(staged)


def test_schema_envelopes_validate_minimal() -> None:
    from transcriptx.core.analysis.topic_shift.semantics import SCHEMA_VERSION

    spans = SpansEnvelopeModel.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_generation_id": "g1",
            "transcript_identity": "abc",
            "semantics_version": "topic_shift_semantics_v1",
            "backend": "tfidf",
            "analytical_status": "no_shift_detected",
            "coverage_spans": [],
            "span_count": 0,
        }
    )
    assert spans.analytical_status == "no_shift_detected"
    events = EventsEnvelopeModel.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_generation_id": "g1",
            "transcript_identity": "abc",
            "semantics_version": "topic_shift_semantics_v1",
            "backend": "tfidf",
            "analytical_status": "no_shift_detected",
            "event_count": 0,
            "events": [],
        }
    )
    assert events.event_count == 0
    stats = StatsEnvelopeModel.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_generation_id": "g1",
            "transcript_identity": "abc",
            "semantics_version": "topic_shift_semantics_v1",
            "backend": "tfidf",
            "analytical_status": "insufficient_content",
            "n_shifts": 0,
            "provenance_compatibility_key": "tfidf||topic_shift_semantics_v1",
        }
    )
    assert stats.n_shifts == 0


def test_deterministic_byte_identity_with_llm_sidecar(tmp_path: Path) -> None:
    """Deterministic envelopes identical whether enrichment runs or not."""
    segs = _two_topic_segments()
    result = run_topic_shift_analysis(
        segs,
        settings={
            "window_size": 4,
            "stride": 2,
            "smooth_width": 1,
            "edge_exclude": 0,
            "min_windows_for_detection": 4,
            "min_gap_windows": 1,
            "min_gap_seconds": 0.0,
            "max_shifts": 8,
            "centroid_radius": 1,
            "centroid_threshold": 0.0,
            "min_text_chars": 1,
            "max_windows_per_chunk": 100,
            "chunk_overlap_windows": 2,
            "min_duration_for_rate_seconds": 1.0,
            "en_model": "unused",
            "multi_model": "unused",
            "batch_size": 8,
            "lru_size": 2,
            "thresholds": {
                "k_mad": 0.0,
                "absolute_floor": 0.0,
                "min_prominence": 0.0,
            },
        },
        generation_id="pending",
        allow_downloads=False,
    )
    spans = result["spans_envelope"]
    events = result["events_envelope"]
    stats = result["stats_envelope"]
    # Stamp fixed generation id for byte compare
    for env in (spans, events, stats):
        env["deterministic_generation_id"] = "fixedgid"

    dig_off = (
        content_digest(spans),
        content_digest(events),
        content_digest(stats),
    )

    module_dir = tmp_path / "topic_shift"
    module_dir.mkdir()
    # Enrichment must not mutate envelopes
    maybe_run_topic_shift_enrichment(
        module_output_dir=module_dir,
        spans_envelope=spans,
        llm_cfg=SimpleNamespace(enabled=True, model="x", model_selection=None),
        llm_enabled=False,
    )
    dig_on_path = (
        content_digest(spans),
        content_digest(events),
        content_digest(stats),
    )
    assert dig_off == dig_on_path


def test_short_duration_shifts_per_hour_null_in_aggregation(tmp_path: Path) -> None:
    path_a = str(tmp_path / "a.json")
    results = [
        PerTranscriptResult(
            transcript_path=path_a,
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "a"),
            module_results={
                "topic_shift": {
                    "stats": {
                        "analytical_status": "success",
                        "n_shifts": 2,
                        "valid_duration_seconds": 30.0,  # below default min
                        "shifts_per_hour": 240.0,
                        "median_span_duration": 10.0,
                        "longest_span_duration": 20.0,
                        "backend": "tfidf",
                        "model_name": None,
                        "semantics_version": "topic_shift_semantics_v1",
                        "provenance_compatibility_key": "tfidf|None|v1",
                    }
                }
            },
        )
    ]
    tset = TranscriptSet.create(
        ["a"], metadata={"transcript_id_map": {path_a: "a"}}
    )
    out = aggregate_topic_shift(results, {}, tset)
    assert out is not None
    row = out["session_rows"][0]
    assert row["included_in_comparison"] is True
    assert row["n_shifts"] == 2
    assert row["shifts_per_hour"] is None


def test_suppress_surface_artifacts_on_failed() -> None:
    arts = [
        SimpleNamespace(module="topic_shift", rel_path="topic_shift/data/x.json"),
        SimpleNamespace(module="moments", rel_path="moments/data/y.json"),
        SimpleNamespace(module=None, rel_path="topic_shift/charts/z.html"),
    ]
    run_results = {
        "modules_enabled": ["topic_shift"],
        "modules_run": [],
        "modules_failed": ["topic_shift"],
        "modules_skipped": [],
    }
    # Use Path that won't load run_results from disk
    filtered = suppress_topic_shift_surface_artifacts(
        arts, run_root=Path("/nonexistent"), run_results=run_results
    )
    assert len(filtered) == 1
    assert filtered[0].module == "moments"


def test_module_save_pipeline_smoke(tmp_path: Path) -> None:
    """End-to-end save through TopicShiftAnalysis + OutputService (offline tfidf)."""
    from transcriptx.core.analysis.topic_shift import TopicShiftAnalysis

    transcript = tmp_path / "mini.json"
    transcript.write_text(
        json.dumps({"segments": _two_topic_segments(20)}), encoding="utf-8"
    )
    out_root = tmp_path / "outputs"
    svc = OutputService(
        str(transcript), "topic_shift", output_dir=str(out_root)
    )
    analysis = TopicShiftAnalysis(
        {
            "window_size": 4,
            "stride": 2,
            "min_windows_for_detection": 4,
            "min_text_chars": 1,
            "allow_downloads": False,
        }
    )
    # Force settings via analyze path
    segs = _two_topic_segments(20)
    results = analysis.analyze(segs)
    # Override settings already applied in analyze via get_config; ensure envelopes exist
    assert "spans_envelope" in results
    analysis._save_results(results, svc)
    data_dir = Path(svc.output_structure.global_data_dir)
    assert (data_dir / "topic_shift.spans.json").is_file()
    assert (data_dir / "topic_shift.events.json").is_file()
    assert (data_dir / "topic_shift.stats.json").is_file()
    # Enrichment sidecar present (skipped when llm off)
    assert (data_dir / "topic_shift.enrichment.json").is_file()


def test_dual_active_matrix_det_active_enrich_fail_keeps_chapters(tmp_path: Path) -> None:
    """Deterministic ACTIVE + enrichment skipped → chapters still visible."""
    run_root = tmp_path / "run"
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    spans = {
        "analytical_status": "success",
        "coverage_spans": [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Opening",
                "time_start": 0.0,
                "time_end": 5.0,
                "viewer_target_source_index": 0,
                "leading_boundary_id": None,
            }
        ],
    }
    (data / "topic_shift.spans.json").write_text(json.dumps(spans), encoding="utf-8")
    enrich = {
        "outcome": "skipped",
        "skip_reason": "llm_disabled",
        "entries": [],
        "ui_mode": "chapter_titles",
    }
    (data / "topic_shift.enrichment.json").write_text(
        json.dumps(enrich), encoding="utf-8"
    )
    rr = {
        "schema_version": 1,
        "run_id": "r1",
        "transcript_key": "sess",
        "modules_enabled": ["topic_shift"],
        "modules_run": ["topic_shift"],
        "modules_failed": [],
        "modules_skipped": [],
        "errors": [],
        "module_outcomes": [
            {"module_id": "topic_shift", "status": "succeeded"},
        ],
    }
    (run_root / "run_results.json").write_text(json.dumps(rr), encoding="utf-8")
    assert resolve_topic_shift_visibility(run_root, run_results=rr) == "show"
    from transcriptx.web.transcript_viewer.chapters import load_chapter_rows

    rows = load_chapter_rows(run_root)
    assert len(rows) == 1
    assert rows[0].title == "Opening"


def test_offline_probe_without_local_weights(monkeypatch) -> None:
    from transcriptx.core.analysis.topic_shift import analyze as analyze_mod

    monkeypatch.setattr(
        analyze_mod,
        "model_weights_locally_available",
        lambda name: False,
    )
    en_ok, multi_ok = analyze_mod._transformers_probe(
        False, en_model="x", multi_model="y"
    )
    assert en_ok is False
    assert multi_ok is False
