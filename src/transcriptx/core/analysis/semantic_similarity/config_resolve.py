"""Resolve ``SemanticSimilarityV2Config`` for a run (presets, mode overlay, cross-field rules)."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from typing import Any, Set

from transcriptx.core.utils.config.analysis import (
    AnalysisConfig,
    SemanticSimilarityV2Config,
)

_DEFAULT_V2 = SemanticSimilarityV2Config()
_ALLOWED_PRESET_KEYS = frozenset(f.name for f in fields(SemanticSimilarityV2Config))


class SemanticV2StrictAdvancedInputsError(Exception):
    """Raised when advanced mode is requested but integration modules are missing."""

    def __init__(self, missing: Set[str]) -> None:
        self.missing = missing
        super().__init__(f"missing_advanced_integrations:{sorted(missing)}")


def _validate_registered_presets(analysis: AnalysisConfig) -> None:
    for name, preset in analysis.semantic_similarity_profiles.items():
        for key in preset:
            if key not in _ALLOWED_PRESET_KEYS:
                raise ValueError(
                    f"Unknown field {key!r} in semantic_similarity_profiles[{name!r}]"
                )


def resolve_semantic_similarity_runtime(
    analysis: AnalysisConfig,
    *,
    modules_in_run: Set[str],
    embedding_cache_root: Path | None = None,
) -> tuple[SemanticSimilarityV2Config, dict[str, Any]]:
    """
    Merge defaults → active preset → per-field user overrides (values that differ
    from dataclass defaults on ``analysis.semantic_similarity``), then overlay
    ``mode`` from ``analysis_mode`` when the preset dict omits ``mode``.
    """
    _validate_registered_presets(analysis)

    profile_name = analysis.active_semantic_similarity_profile
    if profile_name not in analysis.semantic_similarity_profiles:
        raise ValueError(
            f"Unknown active_semantic_similarity_profile: {profile_name!r}"
        )

    diagnostics: dict[str, Any] = {
        "config_warnings": [],
        "advanced_integrations_unavailable": [],
        "mode_requested": None,
        "mode_effective": None,
    }

    preset_raw = dict(analysis.semantic_similarity_profiles[profile_name])
    preset_mode_supplied = "mode" in preset_raw
    preset_kwargs = {k: v for k, v in preset_raw.items() if k in _ALLOWED_PRESET_KEYS}
    # Delegated config uses init=False fields; construct then setattr (not replace).
    cfg = SemanticSimilarityV2Config()
    for key, value in preset_kwargs.items():
        setattr(cfg, key, deepcopy(value))

    user = analysis.semantic_similarity
    for f in fields(SemanticSimilarityV2Config):
        uv = getattr(user, f.name)
        dv = getattr(_DEFAULT_V2, f.name)
        if uv != dv:
            setattr(cfg, f.name, deepcopy(uv))

    if not preset_mode_supplied:
        cfg.mode = "advanced" if analysis.analysis_mode == "full" else "basic"

    diagnostics["mode_requested"] = cfg.mode

    if cfg.mode == "advanced":
        required = {"sentiment", "emotion", "acts"}
        missing = required - set(modules_in_run)
        if missing:
            if cfg.strict_advanced_inputs:
                raise SemanticV2StrictAdvancedInputsError(missing)
            cfg.mode = "basic"
            diagnostics["config_warnings"].append("advanced_mode_degraded_to_basic")
            diagnostics["advanced_integrations_unavailable"] = sorted(missing)

    diagnostics["mode_effective"] = cfg.mode

    if cfg.persist_embeddings:
        root = embedding_cache_root
        if root is None:
            try:
                from transcriptx.core.utils.config import get_config

                out_cfg = get_config()
                root = Path(getattr(out_cfg.output, "base_output_dir", None) or ".")
            except Exception:
                root = Path(".")
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not os.access(str(root), os.W_OK):
                raise OSError("not writable")
        except OSError:
            diagnostics["config_warnings"].append(
                "persist_embeddings_disabled_no_writable_cache"
            )
            cfg.persist_embeddings = False

    if (
        not cfg.use_lexical_prefilter
        and abs(
            cfg.lexical_prefilter_min_jaccard
            - _DEFAULT_V2.lexical_prefilter_min_jaccard
        )
        > 1e-9
    ):
        diagnostics["config_warnings"].append(
            "lexical_prefilter_min_jaccard_set_but_prefilter_off"
        )

    return cfg, diagnostics
