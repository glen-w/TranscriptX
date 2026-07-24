"""Registry parity tests for Pydantic-backed semantic_similarity_v2."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from transcriptx.core.config.models.semantic_similarity_v2 import (
    SemanticSimilarityV2SettingsModel,
)
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.analysis import SemanticSimilarityV2Config

FIXTURES = Path(__file__).resolve().parent / "fixtures"
V2_PREFIX = "analysis.semantic_similarity_v2."


def _v2_keys() -> set[str]:
    return {
        f"{V2_PREFIX}enabled",
        f"{V2_PREFIX}mode",
        f"{V2_PREFIX}model_name",
        f"{V2_PREFIX}batch_size",
        f"{V2_PREFIX}min_text_length_words",
        f"{V2_PREFIX}self_similarity_threshold",
        f"{V2_PREFIX}cross_speaker_similarity_threshold",
        f"{V2_PREFIX}self_time_window_seconds",
        f"{V2_PREFIX}cross_speaker_time_window_seconds",
        f"{V2_PREFIX}max_candidate_pairs",
        f"{V2_PREFIX}top_k_per_segment",
        f"{V2_PREFIX}timeout_seconds",
        f"{V2_PREFIX}persist_embeddings",
        f"{V2_PREFIX}lru_size",
        f"{V2_PREFIX}use_lexical_prefilter",
        f"{V2_PREFIX}lexical_prefilter_min_jaccard",
        f"{V2_PREFIX}strict_advanced_inputs",
        f"{V2_PREFIX}motif_min_cluster_size",
        f"{V2_PREFIX}cross_session_match_threshold",
        f"{V2_PREFIX}min_sessions_for_recurring",
        f"{V2_PREFIX}max_motifs_per_session",
        f"{V2_PREFIX}max_motifs_per_group",
        f"{V2_PREFIX}max_centroid_bytes",
        f"{V2_PREFIX}cluster_eps",
        f"{V2_PREFIX}cluster_min_samples",
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


def test_build_registry_v2_key_set_exact() -> None:
    reg = build_registry()
    v2_keys = {k for k in reg if k.startswith(V2_PREFIX)}
    assert v2_keys == _v2_keys()


def test_build_registry_non_v2_keys_unchanged() -> None:
    reg = build_registry()
    spot_checks = {
        "analysis.sentiment_window_size": 10,
        "output.dynamic_charts": "auto",
        "dashboard.overview_max_items": None,
        "dashboard.duration_hours_threshold_seconds": 3600,
        "dashboard.duration_summary_style": "compact",
    }
    for key, default in spot_checks.items():
        assert key in reg, key
        assert reg[key].default == default


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    pydantic_defaults = SemanticSimilarityV2SettingsModel().model_dump()
    dataclass_defaults = asdict(SemanticSimilarityV2Config())
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
    defaults = get_default_config_dict()["analysis"]["semantic_similarity_v2"]
    assert defaults == golden
