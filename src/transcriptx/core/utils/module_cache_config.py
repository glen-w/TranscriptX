"""
Module cache-affecting configuration selection.
"""

from __future__ import annotations

from typing import Any, Dict

MODULE_CONFIG_ALLOWLIST = {
    "sentiment": [
        "analysis.sentiment_window_size",
        "analysis.sentiment_min_confidence",
    ],
    "emotion": [
        "analysis.emotion.low_coverage_threshold",
        "analysis.emotion.no_hit_rate_warn",
        "analysis.emotion_min_confidence",
        "analysis.emotion_model_name",
    ],
    "contextual_emotion": [
        "analysis.contextual_emotion.profile_id",
        "analysis.contextual_emotion.confidence_threshold",
        "analysis.contextual_emotion.batch_size",
        "analysis.contextual_emotion.release_channel",
    ],
    "fine_grained_emotion": [
        "analysis.fine_grained_emotion.profile_id",
        "analysis.fine_grained_emotion.label_threshold",
        "analysis.fine_grained_emotion.max_labels_per_segment",
        "analysis.fine_grained_emotion.batch_size",
        "analysis.fine_grained_emotion.release_channel",
    ],
    "ner": [
        "analysis.ner_labels",
        "analysis.ner_min_confidence",
        "analysis.ner_include_geocoding",
        "analysis.ner_use_light_model",
        "analysis.ner_max_segments",
        "analysis.ner_batch_size",
    ],
    "wordclouds": [
        "analysis.wordcloud_max_words",
        "analysis.wordcloud_min_font_size",
        "analysis.wordcloud_stopwords",
    ],
    "interactions": [
        "analysis.interaction_overlap_threshold",
        "analysis.interaction_min_gap",
        "analysis.interaction_min_segment_length",
        "analysis.interaction_response_threshold",
        "analysis.interaction_include_responses",
        "analysis.interaction_include_overlaps",
        "analysis.interaction_min_interactions",
        "analysis.interaction_time_window",
    ],
    "entity_sentiment": [
        "analysis.entity_min_mentions",
        "analysis.entity_types",
        "analysis.entity_sentiment_threshold",
    ],
    "conversation_loops": [
        "analysis.loop_max_intermediate_turns",
        "analysis.loop_exclude_monologues",
        "analysis.loop_min_gap",
        "analysis.loop_max_gap",
    ],
    "semantic_similarity": [
        "analysis.semantic_similarity_threshold",
        "analysis.cross_speaker_similarity_threshold",
        "analysis.repetition_min_sentence_length",
        "analysis.repetition_window_size",
    ],
    "semantic_similarity_advanced": [
        "analysis.semantic_similarity_threshold",
        "analysis.cross_speaker_similarity_threshold",
        "analysis.repetition_min_sentence_length",
        "analysis.repetition_window_size",
    ],
    "semantic_similarity_v2": [
        "analysis.semantic_similarity_v2.enabled",
        "analysis.semantic_similarity_v2.mode",
        "analysis.semantic_similarity_v2.model_name",
        "analysis.semantic_similarity_v2.batch_size",
        "analysis.semantic_similarity_v2.min_text_length_words",
        "analysis.semantic_similarity_v2.self_similarity_threshold",
        "analysis.semantic_similarity_v2.cross_speaker_similarity_threshold",
        "analysis.semantic_similarity_v2.self_time_window_seconds",
        "analysis.semantic_similarity_v2.cross_speaker_time_window_seconds",
        "analysis.semantic_similarity_v2.max_candidate_pairs",
        "analysis.semantic_similarity_v2.top_k_per_segment",
        "analysis.semantic_similarity_v2.timeout_seconds",
        "analysis.semantic_similarity_v2.persist_embeddings",
        "analysis.semantic_similarity_v2.lru_size",
        "analysis.semantic_similarity_v2.use_lexical_prefilter",
        "analysis.semantic_similarity_v2.lexical_prefilter_min_jaccard",
        "analysis.semantic_similarity_v2.strict_advanced_inputs",
        "analysis.active_semantic_similarity_v2_profile",
        "analysis.semantic_similarity_v2_profiles",
        "analysis.include_legacy_modules",
    ],
    "topic_modeling": [
        "analysis.topic_modeling_num_topics",
        "analysis.topic_modeling_max_features",
        "analysis.topic_modeling_min_df",
        "analysis.topic_modeling_max_df",
    ],
    "bertopic": [
        "analysis.bertopic.embedding_model",
        "analysis.bertopic.min_topic_size",
        "analysis.bertopic.nr_topics",
        "analysis.bertopic.top_n_words",
        "analysis.bertopic.label_words",
        "analysis.bertopic.calculate_probabilities",
    ],
    "acts": [
        "analysis.act_confidence_threshold",
    ],
    "tics": [
        "analysis.tics_min_confidence",
    ],
    "understandability": [
        "analysis.readability_metrics",
    ],
    "voice_features": [
        "analysis.voice.enabled",
        "analysis.voice.sample_rate",
        "analysis.voice.vad_mode",
        "analysis.voice.pad_s",
        "analysis.voice.max_seconds_for_pitch",
        "analysis.voice.egemaps_enabled",
        "analysis.voice.deep_mode",
        "analysis.voice.deep_model_name",
        "analysis.voice.deep_max_seconds",
        "analysis.voice.store_parquet",
        "analysis.voice.strict_audio_hash",
        "analysis.voice.max_segments_considered",
    ],
    "voice_mismatch": [
        "analysis.voice.mismatch_threshold",
        "analysis.voice.top_k_moments",
        "analysis.voice.include_unnamed_in_global_curves",
    ],
    "voice_tension": [
        "analysis.voice.bin_seconds",
        "analysis.voice.smoothing_alpha",
        "analysis.voice.include_unnamed_in_global_curves",
    ],
    "voice_fingerprint": [
        "analysis.voice.drift_threshold",
        "analysis.voice.top_k_moments",
    ],
    "stats": [],
    "transcript_quality": [
        "analysis.transcript_quality.low_score_threshold",
        "analysis.transcript_quality.max_gap_seconds",
        "analysis.transcript_quality.cluster_merge_seconds",
        "analysis.transcript_quality.max_spans",
        "analysis.transcript_quality.max_clusters",
    ],
}


def _get_attr(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
    return current


def get_cache_affecting_config(
    module_name: str,
    config: Any,
    *,
    fit_scope: str | None = None,
) -> Dict[str, Any]:
    """
    Return cache-fingerprint config for a module.

    For ``bertopic``, callers should pass ``fit_scope`` (``transcript`` | ``group``)
    so transcript and group fits do not collide.
    """
    allowlist = MODULE_CONFIG_ALLOWLIST.get(module_name, [])
    payload: Dict[str, Any] = {}
    for path in allowlist:
        payload[path] = _get_attr(config, path)
    if module_name == "bertopic":
        payload["fit_scope"] = fit_scope or "transcript"
    return payload
