"""Registry parity tests for Pydantic-backed semantic_similarity."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from transcriptx.core.config.models.semantic_similarity import (
    SemanticSimilaritySettingsModel,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import (
    SEMANTIC_SIMILARITY_PREFIX,
    build_registry,
    get_default_config_dict,
)
from transcriptx.core.utils.config.analysis import SemanticSimilarityConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PREFIX = f"{SEMANTIC_SIMILARITY_PREFIX}."


def _semantic_keys() -> set[str]:
    return {
        f"{PREFIX}enabled",
        f"{PREFIX}mode",
        f"{PREFIX}model_name",
        f"{PREFIX}batch_size",
        f"{PREFIX}min_text_length_words",
        f"{PREFIX}self_similarity_threshold",
        f"{PREFIX}cross_speaker_similarity_threshold",
        f"{PREFIX}self_time_window_seconds",
        f"{PREFIX}cross_speaker_time_window_seconds",
        f"{PREFIX}max_candidate_pairs",
        f"{PREFIX}top_k_per_segment",
        f"{PREFIX}timeout_seconds",
        f"{PREFIX}persist_embeddings",
        f"{PREFIX}lru_size",
        f"{PREFIX}use_lexical_prefilter",
        f"{PREFIX}lexical_prefilter_min_jaccard",
        f"{PREFIX}strict_advanced_inputs",
        f"{PREFIX}motif_min_cluster_size",
        f"{PREFIX}cross_session_match_threshold",
        f"{PREFIX}min_sessions_for_recurring",
        f"{PREFIX}max_motifs_per_session",
        f"{PREFIX}max_motifs_per_group",
        f"{PREFIX}max_centroid_bytes",
        f"{PREFIX}cluster_eps",
        f"{PREFIX}cluster_min_samples",
    }


def _load_golden_registry() -> dict[str, dict]:
    return json.loads((FIXTURES / "semantic_v2_registry_golden.json").read_text())


def test_build_registry_v2_matches_golden_snapshot() -> None:
    golden = _load_golden_registry()
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        actual = serialize_field_metadata(reg[key])
        assert actual == expected, f"{key} mismatch: {actual!r} != {expected!r}"


def test_build_registry_semantic_key_set_exact() -> None:
    assert SEMANTIC_SIMILARITY_PREFIX == "analysis.semantic_similarity"
    reg = build_registry()
    keys = {k for k in reg if k.startswith(PREFIX)}
    assert keys == _semantic_keys()


def test_build_registry_non_semantic_keys_unchanged() -> None:
    reg = build_registry()
    spot_checks = {
        "analysis.sentiment_window_size": 10,
        "output.dynamic_charts": "auto",
        "dashboard.overview_max_items": None,
        "dashboard.duration_hours_threshold_seconds": 3600,
        "dashboard.duration_summary_style": "compact",
        "dashboard.transcript_exclude_unnamed_speakers": True,
    }
    for key, default in spot_checks.items():
        assert key in reg, key
        assert reg[key].default == default


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    pydantic_defaults = SemanticSimilaritySettingsModel().model_dump()
    dataclass_defaults = asdict(SemanticSimilarityConfig())
    assert dataclass_defaults == pydantic_defaults


def test_metadata_config_runtime_defaults_unchanged() -> None:
    """MetadataConfig is not in build_registry (not in to_dict); verify runtime defaults."""
    from transcriptx.core.utils.config import TranscriptXConfig

    cfg = TranscriptXConfig()
    assert cfg.metadata.duration_calculation == "max_end"
    assert cfg.metadata.listing_word_count_fallback == "in_memory"
    assert cfg.metadata.auto_refresh_on_write is True


def test_default_config_subtree_matches_golden() -> None:
    golden = json.loads((FIXTURES / "semantic_v2_defaults_golden.json").read_text())
    defaults = get_default_config_dict()["analysis"]["semantic_similarity"]
    assert defaults == golden
