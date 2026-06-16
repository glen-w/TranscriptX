"""Diagnostics counters for v2 runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class StageTimers:
    intake_s: float = 0.0
    embed_s: float = 0.0
    candidates_s: float = 0.0
    similarity_s: float = 0.0
    classify_s: float = 0.0
    cluster_s: float = 0.0
    output_s: float = 0.0


@dataclass
class DiagnosticsCounters:
    segments_total: int = 0
    segments_eligible: int = 0
    segments_deduplicated: int = 0
    skipped_segments: Dict[str, int] = field(default_factory=dict)
    unique_texts_embedded: int = 0
    embedding_cache_hits: int = 0
    embedding_cache_misses: int = 0
    embedding_backend: str | None = None
    embedding_fallback_reason: str | None = None
    transformer_backend_available: bool = False
    model_name: str | None = None
    device: str | None = None
    batch_size: int | None = None
    effective_top_k: int | None = None
    candidate_pairs_generated: int = 0
    pairs_scored: int = 0
    matches_self: int = 0
    matches_cross: int = 0
    timeout_reached: bool = False
    partial_results: bool = False
    mode_requested: str | None = None
    mode_effective: str | None = None
    config_warnings: list[str] = field(default_factory=list)
    advanced_integrations_unavailable: list[str] = field(default_factory=list)
    runtime_seconds_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments_total": self.segments_total,
            "segments_eligible": self.segments_eligible,
            "segments_deduplicated": self.segments_deduplicated,
            "skipped_segments": dict(self.skipped_segments),
            "unique_texts_embedded": self.unique_texts_embedded,
            "embedding_cache_hits": self.embedding_cache_hits,
            "embedding_cache_misses": self.embedding_cache_misses,
            "embedding_backend": self.embedding_backend,
            "embedding_fallback_reason": self.embedding_fallback_reason,
            "transformer_backend_available": self.transformer_backend_available,
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "effective_top_k": self.effective_top_k,
            "candidate_pairs_generated": self.candidate_pairs_generated,
            "pairs_scored": self.pairs_scored,
            "matches_self": self.matches_self,
            "matches_cross": self.matches_cross,
            "timeout_reached": self.timeout_reached,
            "partial_results": self.partial_results,
            "mode_requested": self.mode_requested,
            "mode_effective": self.mode_effective,
            "config_warnings": list(self.config_warnings),
            "advanced_integrations_unavailable": list(
                self.advanced_integrations_unavailable
            ),
            "runtime_seconds_breakdown": dict(self.runtime_seconds_breakdown),
        }
