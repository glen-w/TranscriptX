"""Package init for speaker profile service bridges."""

from __future__ import annotations

from transcriptx.services.speaker_profiles.backfill_from_maps import (
    apply_backfill_plan,
    plan_backfill_from_maps,
    run_backfill_from_maps,
)
from transcriptx.services.speaker_profiles.create_and_name import (
    PartialSuccess,
    create_profile_link_and_name,
    link_existing_profile_and_name,
)
from transcriptx.services.speaker_profiles.link_targets import (
    LinkTarget,
    LinkTargetSet,
    resolve_save_link_mode,
    suggest_link_targets,
)

__all__ = [
    "LinkTarget",
    "LinkTargetSet",
    "PartialSuccess",
    "apply_backfill_plan",
    "create_profile_link_and_name",
    "link_existing_profile_and_name",
    "plan_backfill_from_maps",
    "resolve_save_link_mode",
    "run_backfill_from_maps",
    "suggest_link_targets",
]
