"""Legacy resolver and managed-transcript gate compatibility."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.pipeline.contracts import RunRequest


@dataclass(frozen=True)
class LegacyResolverOutcome:
    applied: bool
    override_path: Path | None
    resolver_invoked: bool


def enforce_managed_transcript_gate(
    transcript_path: str, *, allow_unmanaged: bool
) -> None:
    from transcriptx.io.import_metadata_sidecar import validate_managed_transcript

    managed_validation = validate_managed_transcript(transcript_path)
    if managed_validation.ok or allow_unmanaged:
        return
    raise ValueError(
        "Cannot register non-managed transcript: "
        f"{managed_validation.category.value} ({managed_validation.message})"
    )


def apply_legacy_resolver_compat(
    *, run_dir: Path, request: RunRequest
) -> LegacyResolverOutcome:
    """Preserve monkeypatched resolver hooks used by legacy pipeline tests."""
    from transcriptx.core.config import persistence as config_persistence_module
    from transcriptx.core.config import resolver as config_resolver_module

    if (
        getattr(config_resolver_module.resolve_effective_config, "__module__", "")
        == "transcriptx.core.config.resolver"
    ):
        return LegacyResolverOutcome(
            applied=False, override_path=None, resolver_invoked=False
        )

    override_path: Path | None = None
    draft_override = config_persistence_module.load_draft_override()
    if isinstance(draft_override, dict):
        sanitized = deepcopy(draft_override)
        sanitized.pop("active_workflow_profile", None)
        analysis_section = sanitized.get("analysis")
        if isinstance(analysis_section, dict):
            analysis_section.pop("active_acts_profile", None)
            analysis_section.pop("active_ner_profile", None)
            analysis_section.pop("active_semantic_profile", None)
            analysis_section.pop("active_emotion_profile", None)
            analysis_section.pop("active_voice_profile", None)
        override_path = run_dir / ".legacy_run_override"
        config_persistence_module.save_run_override(override_path, sanitized)

    # The request argument is intentionally part of the explicit compat contract:
    # callers pass the exact request being run, even though current legacy hooks
    # only need run_dir.
    _ = request
    config_resolver_module.resolve_effective_config(run_dir=run_dir)
    return LegacyResolverOutcome(
        applied=True, override_path=override_path, resolver_invoked=True
    )
