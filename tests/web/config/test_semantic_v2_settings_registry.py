"""GUI/registry coverage for semantic_similarity."""

from __future__ import annotations

from transcriptx.core.config.gui_support import (
    COMMON_SETTINGS_SCHEMA,
    PROFILE_TARGET_CONTRACTS,
)
from transcriptx.core.config.registry import build_registry


def _v2_keys() -> set[str]:
    return {
        "analysis.semantic_similarity.enabled",
        "analysis.semantic_similarity.mode",
        "analysis.semantic_similarity.model_name",
        "analysis.semantic_similarity.batch_size",
        "analysis.semantic_similarity.min_text_length_words",
        "analysis.semantic_similarity.self_similarity_threshold",
        "analysis.semantic_similarity.cross_speaker_similarity_threshold",
        "analysis.semantic_similarity.self_time_window_seconds",
        "analysis.semantic_similarity.cross_speaker_time_window_seconds",
        "analysis.semantic_similarity.max_candidate_pairs",
        "analysis.semantic_similarity.top_k_per_segment",
        "analysis.semantic_similarity.timeout_seconds",
        "analysis.semantic_similarity.persist_embeddings",
        "analysis.semantic_similarity.lru_size",
        "analysis.semantic_similarity.use_lexical_prefilter",
        "analysis.semantic_similarity.lexical_prefilter_min_jaccard",
        "analysis.semantic_similarity.strict_advanced_inputs",
        "analysis.semantic_similarity.motif_min_cluster_size",
        "analysis.semantic_similarity.cross_session_match_threshold",
        "analysis.semantic_similarity.min_sessions_for_recurring",
        "analysis.semantic_similarity.max_motifs_per_session",
        "analysis.semantic_similarity.max_motifs_per_group",
        "analysis.semantic_similarity.max_centroid_bytes",
        "analysis.semantic_similarity.cluster_eps",
        "analysis.semantic_similarity.cluster_min_samples",
    }


def test_registry_contains_all_v2_keys_with_descriptions() -> None:
    reg = build_registry()
    for key in _v2_keys():
        assert key in reg, key
        assert reg[key].description


def test_common_settings_schema_groups_semantic_similarity() -> None:
    keys = {f.key for f in COMMON_SETTINGS_SCHEMA}
    for k in _v2_keys():
        assert k in keys, k
    for f in COMMON_SETTINGS_SCHEMA:
        if not f.key.startswith("analysis.semantic_similarity."):
            continue
        assert f.group.startswith("Semantic Similarity /")
        assert "v2" not in f.group.lower()
        assert "v2" not in f.label.lower()


def test_advanced_flags_on_performance_and_filtering() -> None:
    reg = build_registry()
    perf_filter = {
        "analysis.semantic_similarity.batch_size",
        "analysis.semantic_similarity.lru_size",
        "analysis.semantic_similarity.persist_embeddings",
        "analysis.semantic_similarity.min_text_length_words",
        "analysis.semantic_similarity.use_lexical_prefilter",
        "analysis.semantic_similarity.lexical_prefilter_min_jaccard",
    }
    for k in perf_filter:
        assert reg[k].advanced is True, k


def test_profile_target_semantic_similarity_contract() -> None:
    c = PROFILE_TARGET_CONTRACTS["semantic_similarity"]
    assert c.support.config_path == ("analysis", "semantic_similarity")
    assert "enabled" in c.edit_support.guided_fields
    for motif_field in (
        "motif_min_cluster_size",
        "cross_session_match_threshold",
        "min_sessions_for_recurring",
        "max_motifs_per_session",
        "max_motifs_per_group",
        "max_centroid_bytes",
        "cluster_eps",
        "cluster_min_samples",
    ):
        assert motif_field in c.edit_support.guided_fields, motif_field