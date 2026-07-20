"""Tests for cross-session pooled group wordclouds (metadata, pooling semantics)."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.utils.paths import OUTPUTS_DIR

from transcriptx.core.analysis import wordclouds as wordclouds_pkg
from transcriptx.core.analysis.aggregation.wordclouds import (
    aggregate_wordclouds_group,
    build_full_transcript_text_pooled,
)
from transcriptx.core.analysis.wordclouds import analysis as wordclouds_analysis
from transcriptx.core.analysis.wordclouds import pooled_variants
from transcriptx.core.analysis.wordclouds.analysis import run_group_wordclouds
from transcriptx.core.output.group_wordcloud_output_service import (
    CANONICAL_MERGE_BASIS_VALUE,
    GroupWordcloudOutputService,
    WORDCLOUD_GROUP_TAGS,
)
from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.nlp_utils import tokenize_and_filter
from transcriptx.io.transcript_service import TranscriptService


def test_aggregate_summary_includes_merge_basis_and_join_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={},
        ),
    ]
    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={"a.json": {"Alice": 1}},
        canonical_to_display={1: "Alice"},
        transcript_to_display={"a.json": {"Alice": "Alice"}},
    )

    def fake_load(
        self: TranscriptService, transcript_path: str, use_cache: bool = True
    ) -> list[dict]:
        return [{"speaker": "Alice", "text": "hello world"}]

    monkeypatch.setattr(TranscriptService, "load_segments", fake_load)
    _, summary = aggregate_wordclouds_group(results, cmap)

    assert summary is not None
    assert summary["canonical_merge_basis"] == CANONICAL_MERGE_BASIS_VALUE
    assert summary["cross_bucket_global_join_order"] == "sorted_speaker_display_name"


def test_semantic_global_matches_sorted_bucket_concat_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Global pooled text: sorted speaker keys; tokens match tokenize_and_filter."""
    grouped = {"Bob": ["b one"], "Alice": ["a one"]}
    captured: dict[str, str] = {}

    def fake_gw(
        text: str,
        output_structure: Any,
        base_name: str,
        speaker: str,
        filename: str,
        chart_type: str = "basic",
        title: str = "Word Cloud",
        viz_id: str | None = None,
    ) -> dict[str, int]:
        if (
            speaker == "wordcloud-ALL"
            and filename == "wordcloud"
            and viz_id == "wordcloud.pooled_cross_session.basic.global.named_resolved"
        ):
            captured["global_text"] = text
        return {"tok": 1}

    monkeypatch.setattr(wordclouds_analysis, "generate_wordcloud", fake_gw)
    monkeypatch.setattr(wordclouds_analysis, "save_freq_json_csv", lambda *a, **k: None)

    run_group_wordclouds(
        grouped,
        tmp_path,
        "grp",
        "run1",
        group_uuid="uuid-1",
        per_transcript_results=[],
        aggregation_summary={},
    )
    expected = "\n".join(
        {"Alice": "\n".join(["a one"]), "Bob": "\n".join(["b one"])}[s]
        for s in ("Alice", "Bob")
    )
    assert captured.get("global_text") == expected
    assert tokenize_and_filter(captured["global_text"]) == tokenize_and_filter(expected)


def test_build_full_transcript_includes_unnamed_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load(
        self: TranscriptService, transcript_path: str, use_cache: bool = True
    ) -> list[dict]:
        if "y.json" in transcript_path:
            return [{"text": "first line", "start": 0.0}]
        return [
            {"speaker": "SPEAKER_00", "text": "ghost", "start": 1.0},
            {"text": "no speaker", "start": 2.0},
        ]

    monkeypatch.setattr(TranscriptService, "load_segments", fake_load)
    results = [
        PerTranscriptResult(
            transcript_path="x.json",
            transcript_key="x",
            run_id="r",
            order_index=1,
            output_dir="o",
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path="y.json",
            transcript_key="y",
            run_id="r",
            order_index=0,
            output_dir="o",
            module_results={},
        ),
    ]
    text = build_full_transcript_text_pooled(results)
    assert text is not None
    assert text.startswith("first line")
    assert "ghost" in text and "no speaker" in text


def test_group_wordcloud_output_service_records_semantic_metadata() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(OUTPUTS_DIR) / f"_tx_wc_meta_{uuid.uuid4().hex[:10]}"
    out.mkdir(parents=True)
    try:
        virtual = out / "v.virtual"
        svc = GroupWordcloudOutputService(
            transcript_path=str(virtual),
            module_name="wordclouds",
            output_dir=str(out),
            run_id="r1",
            group_uuid="g-uuid",
        )
        svc.prepare_pooled_artifact(
            pooled_view_kind="pooled_basic_cross_session_global_named_resolved",
            pooled_input_basis="named_resolved_buckets_concatenated_global",
            pooled_lexicon_scope="named_and_resolved_speakers_only",
        )
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.plot([0, 1], [0, 1])
        from transcriptx.core.viz.specs import PreRenderedFigureSpec

        svc.save_chart(
            PreRenderedFigureSpec(
                viz_id="wordcloud.test.global",
                module="wordclouds",
                name="wc-test",
                scope="global",
                chart_intent="pre_rendered",
                title="T",
                figure=fig,
                labels=["term"],
                values=[1.0],
            ),
            dpi=72,
            chart_type="basic",
        )

        meta_path = out / ".transcriptx" / "artifacts_meta.json"
        assert meta_path.is_file()
        blob = json.loads(meta_path.read_text(encoding="utf-8"))
        png_keys = [k for k in blob if k.endswith(".png")]
        assert png_keys
        entry = blob[png_keys[0]]
        assert entry.get("pooled_lexicon_scope") == "named_and_resolved_speakers_only"
        assert entry.get("canonical_merge_basis") == CANONICAL_MERGE_BASIS_VALUE
        assert (
            entry.get("pooled_input_basis")
            == "named_resolved_buckets_concatenated_global"
        )
        assert entry.get("agg_id") == "wordclouds"
        assert entry.get("group_uuid") == "g-uuid"
        for t in WORDCLOUD_GROUP_TAGS:
            assert t in (entry.get("tags") or [])
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_manifest_union_includes_group_aggregate_for_pooled_wordcloud() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(OUTPUTS_DIR) / f"_tx_wc_man_{uuid.uuid4().hex[:10]}"
    out.mkdir(parents=True)
    try:
        svc = GroupWordcloudOutputService(
            transcript_path=str(out / "v.virtual"),
            module_name="wordclouds",
            output_dir=str(out),
            run_id="r1",
            group_uuid="gu",
        )
        svc.prepare_pooled_artifact(
            pooled_view_kind="pooled_basic_cross_session_speaker",
            pooled_input_basis="segments_concatenated_per_bucket",
            pooled_lexicon_scope="named_and_resolved_speakers_only",
        )
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.plot([0, 1], [0, 1])
        from transcriptx.core.viz.specs import PreRenderedFigureSpec

        svc.save_chart(
            PreRenderedFigureSpec(
                viz_id="wordcloud.pooled.speaker",
                module="wordclouds",
                name="wc-spk",
                scope="speaker",
                speaker="Alice",
                chart_intent="pre_rendered",
                title="Alice pooled",
                figure=fig,
                labels=["term"],
                values=[1.0],
            ),
            dpi=72,
            chart_type="basic",
        )

        man = build_output_manifest(out, "r1", "gu", ["wordclouds"])
        arts = man.get("artifacts") or []
        static_charts = [a for a in arts if a.get("kind") == "chart_static"]
        assert static_charts
        tags = static_charts[0].get("tags") or []
        assert "group_aggregate" in tags
        assert "pooled_cross_session" in tags
        assert "member_session" not in tags
        title = static_charts[0].get("title") or ""
        assert "Alice" in title
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_pooled_variants_inventory_has_basic_frequency() -> None:
    inv = pooled_variants.POOLED_WORDCLOUD_VARIANT_CLASSIFICATION
    assert "basic_frequency" in inv
    assert inv["basic_frequency"]["pooled_global"] == "safe_for_pooled_global"


def test_run_group_wordclouds_writes_sidecar_with_session_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        wordclouds_analysis, "generate_wordcloud", lambda *a, **k: {"x": 1}
    )
    monkeypatch.setattr(wordclouds_analysis, "save_freq_json_csv", lambda *a, **k: None)

    grouped = {"Sue": ["hi"]}
    members = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r",
            order_index=0,
            output_dir="o",
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path="b.json",
            transcript_key="b",
            run_id="r",
            order_index=1,
            output_dir="o",
            module_results={},
        ),
    ]
    out = run_group_wordclouds(
        grouped,
        tmp_path,
        "base",
        "runx",
        group_uuid="g1",
        per_transcript_results=members,
        aggregation_summary={"excluded_chunks": 0},
    )
    p = out.get("pooled_cross_session_summary_path")
    assert p
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    assert data["session_count"] == 2
    assert data["schema_version"] == 1


def test_pooled_global_tfidf_dispatched_when_config_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    def fake_emit(**kwargs: Any) -> None:
        calls.append(True)

    monkeypatch.setattr(
        wordclouds_analysis,
        "_emit_pooled_global_tfidf_wordcloud",
        fake_emit,
    )
    monkeypatch.setattr(
        wordclouds_analysis, "generate_wordcloud", lambda *a, **k: {"a": 1}
    )
    monkeypatch.setattr(wordclouds_analysis, "save_freq_json_csv", lambda *a, **k: None)

    class _GA:
        wordcloud_pooled_emit_full_transcript_global = False
        wordcloud_pooled_global_tfidf = True

    class _Cfg:
        group_analysis = _GA()

    monkeypatch.setattr(wordclouds_analysis, "get_config", lambda: _Cfg())

    members = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r",
            order_index=0,
            output_dir="o",
            module_results={},
        ),
    ]
    run_group_wordclouds(
        {"A": ["hello"]},
        tmp_path,
        "base",
        "runz",
        group_uuid="g",
        per_transcript_results=members,
        aggregation_summary={},
    )
    assert calls == [True]


def test_wordclouds_package_exports_pooled_variants() -> None:
    assert hasattr(wordclouds_pkg, "pooled_variants")
