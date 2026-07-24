"""Orchestrate semantic_similarity_v2 stages."""

from __future__ import annotations

import time
from typing import Any, Dict, List

import numpy as np

from transcriptx.core.analysis.semantic_similarity.models import SemanticModelManager
from transcriptx.core.utils.config.analysis import SemanticSimilarityV2Config
from transcriptx.core.utils.lazy_imports import get_torch, get_transformers

from .candidates import generate_candidate_pairs
from .classify import classify_pairs
from .cluster import cluster_embeddings
from .diagnostics import DiagnosticsCounters, StageTimers
from .embedding import LRUEmbeddingCache, SemanticBatchEmbedder
from .intake import segment_rows_from_dicts
from .motifs import (
    attach_motif_envelope,
    build_motifs_from_clusters,
    build_provenance,
)
from .output import with_schema
from .similarity import score_pairs

_TFIDF_SIGNATURE = "sklearn_tfidf_max4096_ngram1_2_fit_per_transcript"


def _finalize(
    results: Dict[str, Any],
    *,
    motifs: List[Dict[str, Any]] | None = None,
    motif_export_status: str,
    reason: str | None,
    provenance: Dict[str, Any],
    eligible_segment_count: int,
) -> Dict[str, Any]:
    envelope_motifs = motifs if motifs is not None else []
    attach_motif_envelope(
        results,
        motifs=envelope_motifs,
        motif_export_status=motif_export_status,
        reason=reason,
        provenance=provenance,
        eligible_segment_count=eligible_segment_count,
    )
    return with_schema(results)


def run_semantic_similarity_v2_pipeline(
    segments: List[Dict[str, Any]],
    cfg: SemanticSimilarityV2Config,
    *,
    resolve_diagnostics: Dict[str, Any],
    repetition_path_skipped: bool = False,
) -> tuple[Dict[str, Any], DiagnosticsCounters]:
    diag = DiagnosticsCounters()
    diag.config_warnings = list(resolve_diagnostics.get("config_warnings", []))
    diag.advanced_integrations_unavailable = list(
        resolve_diagnostics.get("advanced_integrations_unavailable", [])
    )
    diag.mode_requested = resolve_diagnostics.get("mode_requested") or cfg.mode
    diag.mode_effective = resolve_diagnostics.get("mode_effective") or cfg.mode
    diag.model_name = cfg.model_name
    diag.batch_size = int(cfg.batch_size)
    diag.effective_top_k = int(cfg.top_k_per_segment)
    timers = StageTimers()
    t_all = time.perf_counter()

    empty_prov = build_provenance(
        embedding_backend=None,
        model_name=cfg.model_name,
        model_revision=None,
        vector_dimension=0,
        fallback_vectorizer_signature=None,
    )

    if not cfg.enabled:
        diag.runtime_seconds_breakdown = {"total": 0.0}
        return (
            _finalize(
                {"skipped": True, "reason": "semantic_similarity_v2_disabled"},
                motif_export_status="skipped",
                reason="semantic_similarity_v2_disabled",
                provenance=empty_prov,
                eligible_segment_count=0,
            ),
            diag,
        )

    t0 = time.perf_counter()
    rows, skip_meta = segment_rows_from_dicts(
        segments, min_words=cfg.min_text_length_words
    )
    timers.intake_s = time.perf_counter() - t0
    diag.segments_total = len(segments)
    diag.segments_eligible = len(rows)
    diag.skipped_segments = skip_meta.get("skipped_reasons", {})

    deadline = time.perf_counter() + float(cfg.timeout_seconds)

    def timed_out() -> bool:
        return time.perf_counter() >= deadline

    if not rows:
        diag.runtime_seconds_breakdown = {"intake": timers.intake_s}
        return (
            _finalize(
                {
                    "speaker_repetitions": {},
                    "cross_speaker_repetitions": [],
                    "segments": segments,
                    "repetition_path": "skipped" if repetition_path_skipped else "ok",
                },
                motif_export_status="valid_zero",
                reason="no_eligible_segments",
                provenance=empty_prov,
                eligible_segment_count=0,
            ),
            diag,
        )

    text_to_urow: dict[str, int] = {}
    unique_texts: list[str] = []
    urow_for_seg: list[int] = []
    for r in rows:
        if r.normalized not in text_to_urow:
            text_to_urow[r.normalized] = len(unique_texts)
            unique_texts.append(r.normalized)
        urow_for_seg.append(text_to_urow[r.normalized])

    n_u = len(unique_texts)
    diag.unique_texts_embedded = n_u
    diag.segments_deduplicated = max(0, len(rows) - n_u)

    t_embed = time.perf_counter()
    cache = LRUEmbeddingCache(cfg.lru_size)
    model_manager = None
    transformer_unavailable_reason = None
    try:
        get_torch()
        get_transformers()
    except (ImportError, ModuleNotFoundError):
        transformer_unavailable_reason = "missing_transformer_dependency"
    else:
        model_manager = SemanticModelManager(
            config=None,
            model_name=cfg.model_name,
            log_tag="SEMANTIC_V2",
        )
        model_manager.initialize()
        if model_manager.model is None or model_manager.tokenizer is None:
            transformer_unavailable_reason = "model_unavailable"
    embedder = SemanticBatchEmbedder(
        cfg.model_name,
        cfg.batch_size,
        cache=cache,
        model_manager=model_manager,
        transformer_unavailable_reason=transformer_unavailable_reason,
    )
    e_unique = embedder.embed_unique_texts(unique_texts)
    diag.embedding_cache_hits = cache.hits
    diag.embedding_cache_misses = cache.misses
    diag.embedding_backend = embedder.embedding_backend
    diag.embedding_fallback_reason = embedder.embedding_fallback_reason
    diag.transformer_backend_available = embedder.transformer_backend_available
    diag.device = embedder.embedding_device
    timers.embed_s = time.perf_counter() - t_embed

    dim = int(e_unique.shape[1]) if e_unique.ndim == 2 and e_unique.size else 0
    model_revision = None
    if model_manager is not None:
        model_revision = getattr(model_manager, "model_revision", None) or getattr(
            model_manager, "revision", None
        )
    fallback_sig = (
        _TFIDF_SIGNATURE if embedder.embedding_backend == "tfidf" else None
    )
    provenance = build_provenance(
        embedding_backend=embedder.embedding_backend,
        model_name=cfg.model_name,
        model_revision=str(model_revision) if model_revision else None,
        vector_dimension=dim,
        fallback_vectorizer_signature=fallback_sig,
    )

    e_seg = e_unique[np.array(urow_for_seg, dtype=np.int64)]

    if timed_out():
        # Plan §4: if e_seg is available, still attempt motif export (partial).
        diag.timeout_reached = True
        diag.partial_results = True
        t_cluster = time.perf_counter()
        cluster_info = cluster_embeddings(
            e_seg,
            min_samples=int(cfg.cluster_min_samples),
            eps=float(cfg.cluster_eps),
        )
        timers.cluster_s = time.perf_counter() - t_cluster
        motifs, m_status, m_reason = build_motifs_from_clusters(
            rows,
            e_seg,
            cluster_info,
            motif_min_cluster_size=int(cfg.motif_min_cluster_size),
            max_motifs_per_session=int(cfg.max_motifs_per_session),
            max_centroid_bytes=int(cfg.max_centroid_bytes),
            provenance=provenance,
        )
        motif_status = (
            "partial"
            if m_status in ("ok", "valid_zero", "partial")
            else m_status
        )
        diag.runtime_seconds_breakdown = {
            "intake": timers.intake_s,
            "embed": timers.embed_s,
            "cluster": timers.cluster_s,
        }
        return (
            _finalize(
                {
                    "speaker_repetitions": {},
                    "cross_speaker_repetitions": [],
                    "segments": segments,
                    "clustering": cluster_info,
                    "mode": cfg.mode,
                    "total_repetitions": 0,
                    "unique_patterns": int(cluster_info.get("n_clusters", 0)),
                    "repetition_path": (
                        "skipped" if repetition_path_skipped else "partial"
                    ),
                },
                motifs=motifs,
                motif_export_status=motif_status,
                reason=m_reason or "timeout_after_embed",
                provenance=provenance,
                eligible_segment_count=len(rows),
            ),
            diag,
        )

    classified: Dict[str, Any] = {
        "speaker_repetitions": {},
        "cross_speaker_repetitions": [],
    }
    if not repetition_path_skipped:
        t_c = time.perf_counter()
        pairs, gen_count = generate_candidate_pairs(
            rows,
            self_window=cfg.self_time_window_seconds,
            cross_window=cfg.cross_speaker_time_window_seconds,
            top_k_per_segment=cfg.top_k_per_segment,
            max_candidate_pairs=cfg.max_candidate_pairs,
            use_lexical_prefilter=cfg.use_lexical_prefilter,
            lexical_min_jaccard=cfg.lexical_prefilter_min_jaccard,
        )
        timers.candidates_s = time.perf_counter() - t_c
        diag.candidate_pairs_generated = gen_count

        if timed_out():
            diag.timeout_reached = True
            diag.partial_results = True
            diag.runtime_seconds_breakdown = {
                "intake": timers.intake_s,
                "embed": timers.embed_s,
                "candidates": timers.candidates_s,
            }
            # Still attempt motif export from embeddings.
            cluster_info = cluster_embeddings(
                e_seg,
                min_samples=int(cfg.cluster_min_samples),
                eps=float(cfg.cluster_eps),
            )
            motifs, m_status, m_reason = build_motifs_from_clusters(
                rows,
                e_seg,
                cluster_info,
                motif_min_cluster_size=int(cfg.motif_min_cluster_size),
                max_motifs_per_session=int(cfg.max_motifs_per_session),
                max_centroid_bytes=int(cfg.max_centroid_bytes),
                provenance=provenance,
            )
            status = "partial" if m_status in ("ok", "valid_zero", "partial") else m_status
            if m_status == "ok" and not motifs:
                status = "partial"
            return (
                _finalize(
                    {
                        **classified,
                        "segments": segments,
                        "clustering": cluster_info,
                        "mode": cfg.mode,
                        "total_repetitions": 0,
                        "unique_patterns": int(cluster_info.get("n_clusters", 0)),
                        "repetition_path": "partial",
                    },
                    motifs=motifs,
                    motif_export_status=status if status != "ok" else "partial",
                    reason=m_reason or "timeout_after_candidates",
                    provenance=provenance,
                    eligible_segment_count=len(rows),
                ),
                diag,
            )

        t_s = time.perf_counter()
        scores = score_pairs(e_seg, pairs)
        timers.similarity_s = time.perf_counter() - t_s
        diag.pairs_scored = len(scores)

        if timed_out():
            diag.timeout_reached = True
            diag.partial_results = True

        t_cl = time.perf_counter()
        classified = classify_pairs(
            rows,
            pairs,
            scores,
            self_threshold=cfg.self_similarity_threshold,
            cross_threshold=cfg.cross_speaker_similarity_threshold,
        )
        diag.matches_self = sum(
            len(v) for v in classified["speaker_repetitions"].values()
        )
        diag.matches_cross = len(classified["cross_speaker_repetitions"])
        timers.classify_s = time.perf_counter() - t_cl
    else:
        diag.candidate_pairs_generated = 0
        diag.pairs_scored = 0
        diag.matches_self = 0
        diag.matches_cross = 0

    t_cluster = time.perf_counter()
    cluster_info = cluster_embeddings(
        e_seg,
        min_samples=int(cfg.cluster_min_samples),
        eps=float(cfg.cluster_eps),
    )
    timers.cluster_s = time.perf_counter() - t_cluster

    motifs, motif_status, motif_reason = build_motifs_from_clusters(
        rows,
        e_seg,
        cluster_info,
        motif_min_cluster_size=int(cfg.motif_min_cluster_size),
        max_motifs_per_session=int(cfg.max_motifs_per_session),
        max_centroid_bytes=int(cfg.max_centroid_bytes),
        provenance=provenance,
    )
    if diag.timeout_reached and motif_status in ("ok", "valid_zero"):
        motif_status = "partial"
        motif_reason = motif_reason or "timeout_partial"

    results = {
        **classified,
        "segments": segments,
        "clustering": cluster_info,
        "mode": cfg.mode,
        "total_repetitions": diag.matches_self + diag.matches_cross,
        "unique_patterns": int(cluster_info.get("n_clusters", 0)),
        "repetition_path": "skipped" if repetition_path_skipped else "ok",
    }

    diag.runtime_seconds_breakdown = {
        "intake": timers.intake_s,
        "embed": timers.embed_s,
        "candidates": timers.candidates_s,
        "similarity": timers.similarity_s,
        "classify": timers.classify_s,
        "cluster": timers.cluster_s,
        "total": time.perf_counter() - t_all,
    }
    return (
        _finalize(
            results,
            motifs=motifs,
            motif_export_status=motif_status,
            reason=motif_reason,
            provenance=provenance,
            eligible_segment_count=len(rows),
        ),
        diag,
    )
