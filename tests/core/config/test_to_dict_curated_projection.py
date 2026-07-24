"""to_dict curated projection contracts (Step 1.8)."""

from __future__ import annotations

import json
from dataclasses import asdict

from transcriptx.core.utils.config import TranscriptXConfig

from .delegation_test_utils import without_transcriptx_env


def test_to_dict_omits_runtime_only_fields() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        snapshot = cfg.to_dict()
    assert "mode" not in snapshot
    assert "use_dag_pipeline" not in snapshot.get("analysis", {})
    assert hasattr(cfg, "mode")
    assert hasattr(cfg.analysis, "use_dag_pipeline")


def test_to_dict_json_dumps_succeeds_and_preserves_python_tuples() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        snapshot = cfg.to_dict()
    # json.dumps accepts tuples (encodes as arrays)
    json.dumps(snapshot)
    # Production snapshot may still contain tuples for nested vectorization etc.
    ngram = snapshot["analysis"]["vectorization"]["ngram_range"]
    assert isinstance(ngram, tuple)
    assert ngram == cfg.analysis.vectorization.ngram_range


def test_to_dict_aliasing_vs_deepcopy_characterization() -> None:
    """Freeze current aliasing: flat lists/dicts alias; nested dataclasses deep-copied."""
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        snapshot = cfg.to_dict()

    # Flat list assigned by reference today
    assert snapshot["analysis"]["ner_labels"] is cfg.analysis.ner_labels
    assert (
        snapshot["analysis"]["quality_filtering_profiles"]
        is cfg.analysis.quality_filtering_profiles
    )

    # Nested dataclass subtree goes through asdict → deep copy
    assert snapshot["analysis"]["pauses"] is not cfg.analysis.pauses
    assert snapshot["analysis"]["pauses"] == asdict(cfg.analysis.pauses)


def test_asdict_analysis_exposes_use_dag_pipeline_but_to_dict_does_not() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    assert "use_dag_pipeline" in asdict(cfg.analysis)
    assert "use_dag_pipeline" not in cfg.to_dict()["analysis"]


_CURATED_ANALYSIS_NESTED_KEYS = (
    "semantic_similarity",
    "topic_modeling",
    "acts",
    "tag_extraction",
    "llm_summary",
    "llm_speaker_summary",
    "llm_action_items",
    "qa_analysis",
    "temporal_dynamics",
    "vectorization",
    "voice",
    "affect_tension",
    "speaker_exemplars",
    "corrections",
    "highlights",
    "summary",
    "bertopic",
    "pauses",
    "echoes",
    "momentum",
    "moments",
)

_ADAPTER_ANALYSIS_ACTIVE_KEYS = (
    "active_topic_modeling_profile",
    "active_semantic_similarity_profile",
    "active_acts_profile",
    "active_tag_extraction_profile",
    "active_qa_analysis_profile",
    "active_temporal_dynamics_profile",
    "active_vectorization_profile",
)


def test_to_dict_includes_adapter_active_profile_keys() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        cfg.analysis.active_acts_profile = "custom-acts"
        cfg.active_workflow_profile = "custom-workflow"
        snapshot = cfg.to_dict()
    analysis = snapshot["analysis"]
    for key in _ADAPTER_ANALYSIS_ACTIVE_KEYS:
        assert key in analysis
    assert analysis["active_acts_profile"] == "custom-acts"
    assert snapshot["active_workflow_profile"] == "custom-workflow"


def test_to_dict_curated_shell_includes_nested_analysis_subtrees() -> None:
    with without_transcriptx_env():
        snapshot = TranscriptXConfig().to_dict()
    analysis = snapshot["analysis"]
    for key in _CURATED_ANALYSIS_NESTED_KEYS:
        assert key in analysis, f"missing curated analysis key: {key}"


def test_to_dict_alias_mutation_hazard_vs_nested_deepcopy() -> None:
    """Flat list/dict aliases live config; nested asdict subtrees do not."""
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        snapshot = cfg.to_dict()

    snapshot["analysis"]["ner_labels"].append("__probe__")
    assert "__probe__" in cfg.analysis.ner_labels

    snapshot["analysis"]["pauses"]["min_long_pause_seconds"] = 999.0
    assert cfg.analysis.pauses.min_long_pause_seconds != 999.0
