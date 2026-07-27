"""Canonical GUI support contracts for phase-1 configuration and profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScopeName = Literal["project", "run"]
ProfileType = Literal["module", "workflow"]


@dataclass(frozen=True)
class CommonSettingField:
    """UX contract for curated, guided-edit configuration keys."""

    key: str
    group: str
    label: str


@dataclass(frozen=True)
class ProfileTargetSupport:
    """Canonical profile target support/activation mapping."""

    target_id: str
    profile_type: ProfileType
    activation_key: str
    activation_path: tuple[str, ...]
    config_path: tuple[str, ...]
    scopes: tuple[ScopeName, ...]
    runtime_loaded: bool = True


@dataclass(frozen=True)
class ProfileEditSupport:
    """Guided-edit field support for one profile target."""

    target_id: str
    guided_fields: tuple[str, ...]
    allow_raw_json_fallback: bool = True


@dataclass(frozen=True)
class ProfileTargetPresentation:
    """Display contract for one profile target."""

    target_label: str
    type_badge: str
    activation_label: str
    scope_labels: dict[ScopeName, str]
    order_index: int


@dataclass(frozen=True)
class ProfileTargetContract:
    """Canonical runtime + presentation contract for one profile target."""

    support: ProfileTargetSupport
    edit_support: ProfileEditSupport
    presentation: ProfileTargetPresentation


COMMON_SETTINGS_SCHEMA: tuple[CommonSettingField, ...] = (
    CommonSettingField(
        key="analysis.semantic_model_name",
        group="Models",
        label="Semantic model name",
    ),
    CommonSettingField(
        key="analysis.emotion_model_name",
        group="Models",
        label="Emotion model name",
    ),
    CommonSettingField(
        key="analysis.sentiment_model_name",
        group="Models",
        label="Sentiment model name",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity_threshold",
        group="Semantics",
        label="Semantic similarity threshold",
    ),
    CommonSettingField(
        key="analysis.cross_speaker_similarity_threshold",
        group="Semantics",
        label="Cross-speaker similarity threshold",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity_method",
        group="Semantics",
        label="Semantic similarity method",
    ),
    CommonSettingField(
        key="analysis.echoes.enable_semantic_paraphrase",
        group="Dynamics",
        label="Enable semantic paraphrase in echoes",
    ),
    CommonSettingField(
        key="workflow.default_config_save_path",
        group="Workflow",
        label="Default config save path",
    ),
    CommonSettingField(
        key="output.dynamic_charts",
        group="Output",
        label="Dynamic chart generation mode",
    ),
    CommonSettingField(
        key="output.dynamic_views",
        group="Output",
        label="Dynamic view generation mode",
    ),
    CommonSettingField(
        key="dashboard.transcript_exclude_unnamed_speakers",
        group="Display",
        label="Exclude unnamed speakers from Transcript view",
    ),
    # Semantic Similarity v2 (grouped UX strings)
    CommonSettingField(
        key="analysis.semantic_similarity.enabled",
        group="Semantic Similarity v2 / General",
        label="Enable semantic similarity v2",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.mode",
        group="Semantic Similarity v2 / General",
        label="Semantic v2 mode",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.model_name",
        group="Semantic Similarity v2 / General",
        label="Semantic v2 embedding model",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.self_similarity_threshold",
        group="Semantic Similarity v2 / Thresholds",
        label="Self-similarity threshold",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.cross_speaker_similarity_threshold",
        group="Semantic Similarity v2 / Thresholds",
        label="Cross-speaker similarity threshold",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.self_time_window_seconds",
        group="Semantic Similarity v2 / Windows and limits",
        label="Self time window (seconds)",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.cross_speaker_time_window_seconds",
        group="Semantic Similarity v2 / Windows and limits",
        label="Cross-speaker time window (seconds)",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.max_candidate_pairs",
        group="Semantic Similarity v2 / Windows and limits",
        label="Max candidate pairs",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.top_k_per_segment",
        group="Semantic Similarity v2 / Windows and limits",
        label="Top-k candidates per segment",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.timeout_seconds",
        group="Semantic Similarity v2 / Windows and limits",
        label="Semantic v2 timeout (seconds)",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.batch_size",
        group="Semantic Similarity v2 / Performance",
        label="Semantic v2 embedding batch size",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.lru_size",
        group="Semantic Similarity v2 / Performance",
        label="Embedding LRU size",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.persist_embeddings",
        group="Semantic Similarity v2 / Performance",
        label="Persist embedding cache",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.min_text_length_words",
        group="Semantic Similarity v2 / Filtering",
        label="Minimum words per segment",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.use_lexical_prefilter",
        group="Semantic Similarity v2 / Filtering",
        label="Use lexical Jaccard prefilter",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.lexical_prefilter_min_jaccard",
        group="Semantic Similarity v2 / Filtering",
        label="Lexical prefilter minimum Jaccard",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.strict_advanced_inputs",
        group="Semantic Similarity v2 / General",
        label="Strict advanced inputs (block if integrations missing)",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.motif_min_cluster_size",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Minimum cluster size for a motif",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.cross_session_match_threshold",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Cross-session motif match threshold",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.min_sessions_for_recurring",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Min sessions for recurring motif",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.max_motifs_per_session",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Max motifs per session",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.max_motifs_per_group",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Max motifs per group / chart top-N",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.max_centroid_bytes",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="Max serialized centroid bytes",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.cluster_eps",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="DBSCAN eps (cosine)",
    ),
    CommonSettingField(
        key="analysis.semantic_similarity.cluster_min_samples",
        group="Semantic Similarity v2 / Motifs (B14)",
        label="DBSCAN min_samples",
    ),
)


PROFILE_TARGET_SUPPORT: dict[str, ProfileTargetSupport] = {
    "topic_modeling": ProfileTargetSupport(
        target_id="topic_modeling",
        profile_type="module",
        activation_key="analysis.active_topic_modeling_profile",
        activation_path=("analysis", "active_topic_modeling_profile"),
        config_path=("analysis", "topic_modeling"),
        scopes=("project", "run"),
    ),
    "semantic_similarity": ProfileTargetSupport(
        target_id="semantic_similarity",
        profile_type="module",
        activation_key="analysis.active_semantic_similarity_profile",
        activation_path=("analysis", "active_semantic_similarity_profile"),
        config_path=("analysis", "semantic_similarity"),
        scopes=("project", "run"),
    ),
    "acts": ProfileTargetSupport(
        target_id="acts",
        profile_type="module",
        activation_key="analysis.active_acts_profile",
        activation_path=("analysis", "active_acts_profile"),
        config_path=("analysis", "acts"),
        scopes=("project", "run"),
    ),
    "tag_extraction": ProfileTargetSupport(
        target_id="tag_extraction",
        profile_type="module",
        activation_key="analysis.active_tag_extraction_profile",
        activation_path=("analysis", "active_tag_extraction_profile"),
        config_path=("analysis", "tag_extraction"),
        scopes=("project", "run"),
    ),
    "qa_analysis": ProfileTargetSupport(
        target_id="qa_analysis",
        profile_type="module",
        activation_key="analysis.active_qa_analysis_profile",
        activation_path=("analysis", "active_qa_analysis_profile"),
        config_path=("analysis", "qa_analysis"),
        scopes=("project", "run"),
    ),
    "temporal_dynamics": ProfileTargetSupport(
        target_id="temporal_dynamics",
        profile_type="module",
        activation_key="analysis.active_temporal_dynamics_profile",
        activation_path=("analysis", "active_temporal_dynamics_profile"),
        config_path=("analysis", "temporal_dynamics"),
        scopes=("project", "run"),
    ),
    "vectorization": ProfileTargetSupport(
        target_id="vectorization",
        profile_type="module",
        activation_key="analysis.active_vectorization_profile",
        activation_path=("analysis", "active_vectorization_profile"),
        config_path=("analysis", "vectorization"),
        scopes=("project", "run"),
    ),
    "llm_models": ProfileTargetSupport(
        target_id="llm_models",
        profile_type="module",
        activation_key="llm.active_model_profile",
        activation_path=("llm", "active_model_profile"),
        config_path=("llm", "model_selection"),
        scopes=("project", "run"),
    ),
    "workflow": ProfileTargetSupport(
        target_id="workflow",
        profile_type="workflow",
        activation_key="active_workflow_profile",
        activation_path=("active_workflow_profile",),
        config_path=("workflow",),
        scopes=("project", "run"),
    ),
}


PROFILE_EDIT_SUPPORT: dict[str, ProfileEditSupport] = {
    "topic_modeling": ProfileEditSupport(
        target_id="topic_modeling",
        guided_fields=("max_features", "min_df", "max_df", "ngram_range", "k_range"),
    ),
    "semantic_similarity": ProfileEditSupport(
        target_id="semantic_similarity",
        guided_fields=(
            "enabled",
            "mode",
            "model_name",
            "batch_size",
            "min_text_length_words",
            "self_similarity_threshold",
            "cross_speaker_similarity_threshold",
            "self_time_window_seconds",
            "cross_speaker_time_window_seconds",
            "max_candidate_pairs",
            "top_k_per_segment",
            "timeout_seconds",
            "persist_embeddings",
            "lru_size",
            "use_lexical_prefilter",
            "lexical_prefilter_min_jaccard",
            "strict_advanced_inputs",
        ),
    ),
    "acts": ProfileEditSupport(
        target_id="acts",
        guided_fields=("method", "min_confidence", "ml_model_name", "ml_batch_size"),
    ),
    "tag_extraction": ProfileEditSupport(
        target_id="tag_extraction",
        guided_fields=("early_window_seconds", "early_segments", "min_confidence"),
    ),
    "qa_analysis": ProfileEditSupport(
        target_id="qa_analysis",
        guided_fields=(
            "response_time_threshold",
            "weight_directness",
            "weight_completeness",
            "min_match_threshold",
        ),
    ),
    "temporal_dynamics": ProfileEditSupport(
        target_id="temporal_dynamics",
        guided_fields=(
            "window_size",
            "opening_phase_percentage",
            "closing_phase_percentage",
        ),
    ),
    "vectorization": ProfileEditSupport(
        target_id="vectorization",
        guided_fields=("max_features", "min_df", "max_df", "ngram_range"),
    ),
    "llm_models": ProfileEditSupport(
        target_id="llm_models",
        guided_fields=("mode", "shared_model"),
        allow_raw_json_fallback=True,
    ),
    "workflow": ProfileEditSupport(
        target_id="workflow",
        guided_fields=(
            "timeout_quick_seconds",
            "timeout_full_seconds",
            "update_interval",
        ),
    ),
}

PROFILE_TARGET_ORDER: tuple[str, ...] = (
    "workflow",
    "topic_modeling",
    "semantic_similarity",
    "acts",
    "tag_extraction",
    "qa_analysis",
    "temporal_dynamics",
    "vectorization",
    "llm_models",
)


def build_profile_target_contracts() -> dict[str, ProfileTargetContract]:
    """Build canonical target contracts from support/edit/order maps."""
    order_lookup = {target_id: ix for ix, target_id in enumerate(PROFILE_TARGET_ORDER)}
    contracts: dict[str, ProfileTargetContract] = {}
    for target_id, support in PROFILE_TARGET_SUPPORT.items():
        edit_support = PROFILE_EDIT_SUPPORT.get(
            target_id,
            ProfileEditSupport(
                target_id=target_id, guided_fields=(), allow_raw_json_fallback=True
            ),
        )
        type_badge = "Workflow" if support.profile_type == "workflow" else "Module"
        if target_id == "llm_models":
            type_badge = "LLM"
            target_label = "LLM models"
            activation_label = "Active LLM model profile"
        else:
            target_label = target_id
            activation_label = (
                "Active workflow profile"
                if support.profile_type == "workflow"
                else f"Active profile for `{target_id}`"
            )
        contracts[target_id] = ProfileTargetContract(
            support=support,
            edit_support=edit_support,
            presentation=ProfileTargetPresentation(
                target_label=target_label,
                type_badge=type_badge,
                activation_label=activation_label,
                scope_labels={"project": "Project", "run": "Run override"},
                order_index=order_lookup.get(target_id, len(PROFILE_TARGET_ORDER)),
            ),
        )
    return contracts


PROFILE_TARGET_CONTRACTS: dict[str, ProfileTargetContract] = (
    build_profile_target_contracts()
)


def list_runtime_profile_targets() -> tuple[ProfileTargetSupport, ...]:
    """Return profile targets that are runtime-loadable."""
    return tuple(
        PROFILE_TARGET_CONTRACTS[target_id].support
        for target_id in PROFILE_TARGET_ORDER
        if target_id in PROFILE_TARGET_CONTRACTS
        and PROFILE_TARGET_CONTRACTS[target_id].support.runtime_loaded
    )


def list_supported_profile_target_ids() -> tuple[str, ...]:
    """Return canonical supported profile target ids."""
    ordered = [
        target_id
        for target_id in PROFILE_TARGET_ORDER
        if target_id in PROFILE_TARGET_CONTRACTS
    ]
    # Deterministic non-alpha fallback: insertion order from canonical contracts map.
    unordered = [
        target_id
        for target_id in PROFILE_TARGET_CONTRACTS
        if target_id not in PROFILE_TARGET_ORDER
    ]
    return tuple(ordered + unordered)
