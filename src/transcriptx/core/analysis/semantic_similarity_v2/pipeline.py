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
from .similarity import score_pairs


def run_semantic_similarity_v2_pipeline(
    segments: List[Dict[str, Any]],
    cfg: SemanticSimilarityV2Config,
    *,
    resolve_diagnostics: Dict[str, Any],
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

    if not cfg.enabled:
        diag.runtime_seconds_breakdown = {"total": 0.0}
        return {"skipped": True, "reason": "semantic_similarity_v2_disabled"}, diag

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
        return {
            "speaker_repetitions": {},
            "cross_speaker_repetitions": [],
            "segments": segments,
        }, diag

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

    if timed_out():
        diag.timeout_reached = True
        diag.partial_results = True
        diag.runtime_seconds_breakdown = {
            "intake": timers.intake_s,
            "embed": timers.embed_s,
        }
        return {
            "speaker_repetitions": {},
            "cross_speaker_repetitions": [],
            "segments": segments,
        }, diag

    e_seg = e_unique[np.array(urow_for_seg, dtype=np.int64)]

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
        return {
            "speaker_repetitions": {},
            "cross_speaker_repetitions": [],
            "segments": segments,
        }, diag

    t_s = time.perf_counter()
    scores = score_pairs(e_seg, pairs)
    timers.similarity_s = time.perf_counter() - t_s
    diag.pairs_scored = len(scores)

    if timed_out():
        diag.timeout_reached = True
        diag.partial_results = True
        diag.runtime_seconds_breakdown = {
            "intake": timers.intake_s,
            "embed": timers.embed_s,
            "candidates": timers.candidates_s,
            "similarity": timers.similarity_s,
        }
        return {
            "speaker_repetitions": {},
            "cross_speaker_repetitions": [],
            "segments": segments,
            "clustering": {"labels": [], "n_clusters": 0},
            "mode": cfg.mode,
            "total_repetitions": 0,
            "unique_patterns": 0,
        }, diag

    t_cl = time.perf_counter()
    classified = classify_pairs(
        rows,
        pairs,
        scores,
        self_threshold=cfg.self_similarity_threshold,
        cross_threshold=cfg.cross_speaker_similarity_threshold,
    )
    diag.matches_self = sum(len(v) for v in classified["speaker_repetitions"].values())
    diag.matches_cross = len(classified["cross_speaker_repetitions"])
    timers.classify_s = time.perf_counter() - t_cl

    if timed_out():
        diag.timeout_reached = True
        diag.partial_results = True
        diag.runtime_seconds_breakdown = {
            "intake": timers.intake_s,
            "embed": timers.embed_s,
            "candidates": timers.candidates_s,
            "similarity": timers.similarity_s,
            "classify": timers.classify_s,
        }
        return {
            **classified,
            "segments": segments,
            "clustering": {"labels": [], "n_clusters": 0},
            "mode": cfg.mode,
            "total_repetitions": diag.matches_self + diag.matches_cross,
            "unique_patterns": 0,
        }, diag

    t_cluster = time.perf_counter()
    cluster_info = cluster_embeddings(e_seg)
    timers.cluster_s = time.perf_counter() - t_cluster

    results = {
        **classified,
        "segments": segments,
        "clustering": cluster_info,
        "mode": cfg.mode,
        "total_repetitions": diag.matches_self + diag.matches_cross,
        "unique_patterns": int(cluster_info.get("n_clusters", 0)),
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
    return results, diag
