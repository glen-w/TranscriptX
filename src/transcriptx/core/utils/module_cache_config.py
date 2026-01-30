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
        "analysis.emotion_min_confidence",
        "analysis.emotion_model_name",
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
    "topic_modeling": [
        "analysis.topic_modeling_num_topics",
        "analysis.topic_modeling_max_features",
        "analysis.topic_modeling_min_df",
        "analysis.topic_modeling_max_df",
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
}


def _get_attr(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
    return current


def get_cache_affecting_config(module_name: str, config: Any) -> Dict[str, Any]:
    allowlist = MODULE_CONFIG_ALLOWLIST.get(module_name, [])
    payload: Dict[str, Any] = {}
    for path in allowlist:
        payload[path] = _get_attr(config, path)
    return payload
