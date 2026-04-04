"""Pooled / group wordcloud orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from transcriptx.core.analysis.wordclouds.frequencies import save_freq_json_csv
from transcriptx.core.analysis.wordclouds.output_bridge import (
    _ACTIVE_OUTPUT_SERVICE,
    _relative_to_transcript,
    save_global_chart,
    use_output_service,
)
from transcriptx.core.analysis.wordclouds.plotting import (
    _get_wordcloud_class,
    _save_wordcloud_view,
    _wordcloud_figure,
)
from transcriptx.core.analysis.wordclouds.terms_io import (
    _build_terms_payload,
    _save_terms_json,
)
from transcriptx.core.output.group_wordcloud_output_service import (
    GroupWordcloudOutputService,
)
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.nlp_utils import tokenize_and_filter
from transcriptx.core.utils.output_standards import create_standard_output_structure

plt = lazy_pyplot()


def _emit_pooled_global_tfidf_wordcloud(
    *,
    per_transcript_results: List[Any],
    output_structure: Any,
    base_name: str,
    skipped_variants: List[Dict[str, Any]],
) -> None:
    """Pooled global TF-IDF: one sklearn document per member transcript; mean TF-IDF vector."""
    import transcriptx.core.analysis.wordclouds.analysis as _wc_analysis

    from transcriptx.core.analysis.aggregation.wordclouds import segment_order_key
    from transcriptx.io.transcript_service import TranscriptService

    config = _wc_analysis.get_config()
    vector_config = config.analysis.vectorization
    ts = TranscriptService(enable_cache=True)
    docs: List[str] = []
    for r in sorted(per_transcript_results, key=lambda x: x.order_index):
        if not r.transcript_path:
            continue
        segs = ts.load_segments(r.transcript_path, use_cache=True)
        segs = sorted(segs, key=segment_order_key)
        parts: List[str] = []
        for s in segs:
            tx = s.get("text", "")
            if tx and str(tx).strip():
                parts.append(" ".join(str(tx).split()))
        joined = " ".join(parts)
        docs.append(" ".join(tokenize_and_filter(joined)))
    docs = [d for d in docs if d.strip()]
    if len(docs) < 1:
        skipped_variants.append(
            {
                "variant": "pooled_global_tfidf",
                "reason_code": "NO_DOCUMENTS",
                "message": "No non-empty member transcripts for pooled TF-IDF.",
            }
        )
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        skipped_variants.append(
            {
                "variant": "pooled_global_tfidf",
                "reason_code": "MISSING_SKLEARN",
                "message": "sklearn not installed.",
            }
        )
        return
    try:
        vec = TfidfVectorizer(
            ngram_range=vector_config.wordcloud_ngram_range,
            max_features=vector_config.wordcloud_max_features,
        )
        matrix = vec.fit_transform(docs)
    except ValueError as e:
        if "empty vocabulary" in str(e).lower():
            skipped_variants.append(
                {
                    "variant": "pooled_global_tfidf",
                    "reason_code": "EMPTY_VOCABULARY",
                    "message": str(e),
                }
            )
            return
        raise
    features = vec.get_feature_names_out()
    scores = np.asarray(matrix.mean(axis=0)).ravel()
    freq: Dict[str, float] = {
        str(features[i]): float(scores[i]) for i in range(len(scores)) if scores[i] > 0
    }
    if not freq:
        skipped_variants.append(
            {
                "variant": "pooled_global_tfidf",
                "reason_code": "NO_SCORES",
                "message": "TF-IDF produced no positive weights.",
            }
        )
        return

    svc = _ACTIVE_OUTPUT_SERVICE
    if not isinstance(svc, GroupWordcloudOutputService):
        return
    svc.prepare_pooled_artifact(
        pooled_view_kind="pooled_global_tfidf_mean_across_transcripts",
        pooled_input_basis="tfidf_one_document_per_member_transcript_mean_axis",
        pooled_lexicon_scope="member_transcript_full_text_per_sklearn_document_mean_tfidf",
    )
    wc = _get_wordcloud_class()(
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(freq)
    fig, ax = _wordcloud_figure(wc)
    chart_path = None
    title = "Cross-session pooled TF-IDF (mean across member transcripts)"
    viz_id = "wordcloud.pooled_cross_session.tfidf.global.mean_docs"
    try:
        ax.set_title(title)
        fig.tight_layout()
        chart_path = save_global_chart(
            fig,
            output_structure,
            base_name,
            "tfidf-pooled-global",
            dpi=300,
            chart_type="tfidf",
            title=title,
            viz_id=viz_id,
        )
    finally:
        plt.close(fig)

    payload = _build_terms_payload(
        {k: float(v) for k, v in freq.items()},
        variant="tfidf",
        variant_key="tfidf_pooled_global_mean_docs",
        speaker=None,
        ngram=1,
        metric="tfidf",
    )
    terms_path = _save_terms_json(payload, filename="tfidf-pooled-global", speaker=None)
    _save_wordcloud_view(
        payload,
        title=title,
        filename="tfidf-pooled-global",
        speaker=None,
        source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
        thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
    )


def run_group_wordclouds(
    grouped: Dict[str, List[str]],
    group_base_dir: str | Path,
    base_name: str,
    run_id: str,
    tic_list: list[str] | None = None,
    *,
    group_uuid: str | None = None,
    per_transcript_results: List[Any] | None = None,
    aggregation_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    from transcriptx.core.analysis.aggregation.wordclouds import (
        build_full_transcript_text_pooled,
    )
    from transcriptx.core.utils.logger import get_logger

    logger = get_logger()
    import transcriptx.core.analysis.wordclouds.analysis as _wc_analysis

    skipped_variants: List[Dict[str, Any]] = []
    out: Dict[str, Any] = {"skipped_variants": skipped_variants}

    if not grouped:
        logger.warning("[WORDCLOUDS] No grouped text for group wordclouds.")
        return out

    output_structure = create_standard_output_structure(
        str(group_base_dir), "wordclouds"
    )
    virtual_path = str(Path(group_base_dir) / f"{base_name}.virtual")
    config = _wc_analysis.get_config()
    ga = config.group_analysis
    output_service = GroupWordcloudOutputService(
        transcript_path=virtual_path,
        module_name="wordclouds",
        output_dir=str(group_base_dir),
        run_id=run_id,
        group_uuid=group_uuid,
    )

    def _normalize_chunk(text: str) -> str:
        return " ".join(text.split())

    grouped_joined: Dict[str, str] = {}
    for speaker, chunks in grouped.items():
        cleaned = [
            _normalize_chunk(chunk) for chunk in chunks if chunk and chunk.strip()
        ]
        if not cleaned:
            continue
        grouped_joined[speaker] = "\n".join(cleaned)

    if not grouped_joined:
        logger.warning("[WORDCLOUDS] No non-empty text for group wordclouds.")
        return out

    session_count = (
        len(per_transcript_results)
        if per_transcript_results is not None
        else len(grouped_joined)
    )

    with use_output_service(output_service):
        speakers_sorted = sorted(grouped_joined.keys())
        for speaker in speakers_sorted:
            joined = grouped_joined[speaker]
            output_service.prepare_pooled_artifact(
                pooled_view_kind="pooled_basic_cross_session_speaker",
                pooled_input_basis="segments_concatenated_per_bucket",
                pooled_lexicon_scope="named_and_resolved_speakers_only",
            )
            title = f"{speaker} (cross-session pooled, named + resolved)"
            viz_id = "wordcloud.pooled_cross_session.basic.speaker.named_resolved"
            freq = _wc_analysis.generate_wordcloud(
                joined,
                output_structure,
                base_name,
                speaker,
                "wordcloud",
                chart_type="basic",
                title=title,
                viz_id=viz_id,
            )
            if freq:
                save_freq_json_csv(
                    freq, output_structure, f"{base_name}-basic", speaker
                )

        all_text = "\n".join(grouped_joined[s] for s in speakers_sorted)
        if all_text.strip():
            output_service.prepare_pooled_artifact(
                pooled_view_kind="pooled_basic_cross_session_global_named_resolved",
                pooled_input_basis="named_resolved_buckets_concatenated_global",
                pooled_lexicon_scope="named_and_resolved_speakers_only",
            )
            g_title = (
                "All speakers — named + resolved only, cross-session pooled "
                "(not full transcript)"
            )
            g_viz = "wordcloud.pooled_cross_session.basic.global.named_resolved"
            global_freq = _wc_analysis.generate_wordcloud(
                all_text,
                output_structure,
                base_name,
                "wordcloud-ALL",
                "wordcloud",
                chart_type="basic",
                title=g_title,
                viz_id=g_viz,
            )
            if global_freq:
                save_freq_json_csv(
                    global_freq, output_structure, f"{base_name}-basic", "ALL"
                )
        else:
            logger.warning("[WORDCLOUDS] No text content for global wordcloud")

        if ga.wordcloud_pooled_emit_full_transcript_global and per_transcript_results:
            full_text = build_full_transcript_text_pooled(per_transcript_results)
            if full_text and full_text.strip():
                output_service.prepare_pooled_artifact(
                    pooled_view_kind="pooled_basic_cross_session_global_full_transcript",
                    pooled_input_basis="segments_concatenated_all_members_ordered",
                    pooled_lexicon_scope="full_transcript_including_unidentified",
                )
                ft_title = (
                    "Full transcript — cross-session pooled "
                    "(includes unidentified / unmapped)"
                )
                ft_viz = "wordcloud.pooled_cross_session.basic.global.full_transcript"
                ft_freq = _wc_analysis.generate_wordcloud(
                    full_text,
                    output_structure,
                    base_name,
                    "wordcloud-ALL",
                    "wordcloud-full-transcript",
                    chart_type="basic",
                    title=ft_title,
                    viz_id=ft_viz,
                )
                if ft_freq:
                    save_freq_json_csv(
                        ft_freq,
                        output_structure,
                        f"{base_name}-basic-full-transcript",
                        "ALL",
                    )
            else:
                skipped_variants.append(
                    {
                        "variant": "pooled_full_transcript_global",
                        "reason_code": "NO_TEXT",
                        "message": "No segment text for full-transcript pooled cloud.",
                    }
                )

        if ga.wordcloud_pooled_global_tfidf and per_transcript_results:
            _wc_analysis._emit_pooled_global_tfidf_wordcloud(
                per_transcript_results=per_transcript_results,
                output_structure=output_structure,
                base_name=base_name,
                skipped_variants=skipped_variants,
            )

    sidecar: Dict[str, Any] = {
        "schema_version": 1,
        "session_count": session_count,
        "cross_bucket_global_join_order": "sorted_speaker_display_name",
        "member_transcript_order": "order_index",
        "segment_order_within_transcript": "timestamp_then_stable_list",
        "skipped_variants": skipped_variants,
    }
    if aggregation_summary:
        sidecar["aggregate_exclusions"] = {
            k: aggregation_summary[k]
            for k in (
                "excluded_speakers",
                "excluded_chunks",
                "excluded_chars",
                "global_includes_unidentified",
                "canonical_merge_basis",
                "cross_bucket_global_join_order",
            )
            if k in aggregation_summary
        }
    sidecar_path = (
        output_structure.global_data_dir
        / f"{base_name}_pooled_cross_session_summary.json"
    )
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(sidecar_path, sidecar, indent=2, ensure_ascii=False)
    out["pooled_cross_session_summary_path"] = str(sidecar_path)
    out["skipped_variants"] = skipped_variants
    return out
