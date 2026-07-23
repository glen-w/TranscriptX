"""One-off / maintenance backfill: speaker-map names → longitudinal profiles.

Scans managed library transcripts, reads effective (non-placeholder) speaker-map
names, and creates profile links. Optional merge-by-display-name attaches later
occurrences to the first matching active profile.

Does not rewrite speaker-map sidecars. Safe to re-run (idempotent op keys;
already-linked occurrences are skipped).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from transcriptx.core.speaker_profiles.aggregates import list_profiles
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.identity import (
    link_file_key,
    local_speaker_key_from_raw,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    is_effective_speaker_name,
    normalize_diarized_id,
)

BackfillAction = Literal[
    "create",
    "link",
    "skip_already_linked",
    "skip_ambiguous_name",
    "skip_not_named",
    "skip_excluded_name",
    "skip_ignored",
    "skip_resolver",
    "error",
]

# Local-context role / bucket labels that should stay in speaker maps only.
DEFAULT_EXCLUDED_DISPLAY_NAMES: frozenset[str] = frozenset(
    {
        "audience",
        "academia",
        "interviewer",
        "student",
        "moderator",
        "misc",
        "fan",
        "unknown",
        "unknown_speaker",
        "unidentified",
        "unidentified speaker",
    }
)


def _name_key(display_name: str) -> str:
    return display_name.strip().casefold()


def _normalize_exclude_names(names: set[str] | frozenset[str] | None) -> frozenset[str]:
    if not names:
        return frozenset()
    return frozenset(_name_key(n) for n in names if str(n).strip())


def is_excluded_backfill_display_name(
    display_name: str,
    *,
    exclude_names: set[str] | frozenset[str] | None = None,
    require_named_speaker: bool = True,
) -> bool:
    """True when a display name should not become a longitudinal profile."""
    from transcriptx.utils.text_utils import is_named_speaker

    name = display_name.strip()
    if not name:
        return True
    if require_named_speaker and not is_named_speaker(name):
        return True
    excluded = (
        _normalize_exclude_names(exclude_names)
        if exclude_names is not None
        else DEFAULT_EXCLUDED_DISPLAY_NAMES
    )
    return _name_key(name) in excluded


@dataclass(frozen=True)
class BackfillPlanItem:
    transcript_path: Path
    managed_transcript_id: str | None
    local_speaker_key: str
    display_name: str
    action: BackfillAction
    target_profile_id: str | None = None
    detail: str | None = None


@dataclass
class BackfillResult:
    items: list[BackfillPlanItem] = field(default_factory=list)
    applied: list[BackfillPlanItem] = field(default_factory=list)
    errors: list[BackfillPlanItem] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.items:
            out[item.action] = out.get(item.action, 0) + 1
        return out


def _seed_name_index(
    *,
    root: Path,
    merge_by_name: bool,
) -> dict[str, str | None]:
    """Map casefolded display name → profile_id, or None if ambiguous."""
    index: dict[str, str | None] = {}
    if not merge_by_name:
        return index
    for item in list_profiles(root=root):
        if item.status != "active":
            continue
        key = _name_key(item.display_name)
        if not key:
            continue
        if key in index and index[key] != item.profile_id:
            index[key] = None
        else:
            index[key] = item.profile_id
    return index


def plan_backfill_from_maps(
    *,
    service: SpeakerProfileService | None = None,
    resolver: ManagedTranscriptResolver | None = None,
    map_resolver: SpeakerMapResolver | None = None,
    transcript_paths: list[Path] | None = None,
    merge_by_name: bool = True,
    exclude_names: set[str] | frozenset[str] | None = None,
    require_named_speaker: bool = True,
) -> BackfillResult:
    """Build a dry-runnable plan without mutating the profile store.

    ``exclude_names`` defaults to :data:`DEFAULT_EXCLUDED_DISPLAY_NAMES` when
    omitted or empty. Pass a custom set to replace the default denylist.
    When ``require_named_speaker`` is True (default), labels rejected by
    ``is_named_speaker`` (e.g. ``speaker_00``, ``unknown``) are also skipped.
    """
    svc = service or SpeakerProfileService()
    res = resolver or svc.resolver
    maps = map_resolver or SpeakerMapResolver()
    paths = (
        list(transcript_paths)
        if transcript_paths is not None
        else discover_managed_transcript_paths(None)
    )
    excluded = (
        _normalize_exclude_names(exclude_names)
        if exclude_names is not None
        else DEFAULT_EXCLUDED_DISPLAY_NAMES
    )

    name_index = _seed_name_index(root=svc.root, merge_by_name=merge_by_name)
    result = BackfillResult()

    for path in sorted(paths, key=lambda p: str(p)):
        try:
            resolved = res.resolve_path(path)
        except Exception as exc:
            result.items.append(
                BackfillPlanItem(
                    transcript_path=path,
                    managed_transcript_id=None,
                    local_speaker_key="",
                    display_name="",
                    action="skip_resolver",
                    detail=str(exc),
                )
            )
            continue

        state = maps.load_mapping(path)
        ignored = {
            normalize_diarized_id(s)
            for s in (state.ignored_speakers or [])
            if normalize_diarized_id(s)
        }

        # Prefer map keys; also surface ignored-only entries if needed.
        speaker_ids = sorted(
            {
                normalize_diarized_id(k)
                for k in (state.speaker_map or {})
                if normalize_diarized_id(k)
            }
            | ignored
        )

        for raw_id in speaker_ids:
            try:
                local_key = local_speaker_key_from_raw(raw_id)
            except SpeakerProfileContractError as exc:
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=str(raw_id),
                        display_name="",
                        action="error",
                        detail=str(exc),
                    )
                )
                continue

            display = (state.speaker_map or {}).get(raw_id) or (
                state.speaker_map or {}
            ).get(local_key, "")
            display = str(display).strip()

            if local_key in ignored:
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=local_key,
                        display_name=display,
                        action="skip_ignored",
                    )
                )
                continue

            if not is_effective_speaker_name(local_key, display):
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=local_key,
                        display_name=display,
                        action="skip_not_named",
                    )
                )
                continue

            if is_excluded_backfill_display_name(
                display,
                exclude_names=excluded,
                require_named_speaker=require_named_speaker,
            ):
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=local_key,
                        display_name=display,
                        action="skip_excluded_name",
                        detail="generic/role label excluded from profile backfill",
                    )
                )
                continue

            key = link_file_key(resolved.managed_transcript_id, local_key)
            existing = svc.get_live_link(key)
            if existing is not None:
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=local_key,
                        display_name=display,
                        action="skip_already_linked",
                        target_profile_id=existing.profile_id,
                    )
                )
                continue

            nk = _name_key(display)
            if merge_by_name and nk in name_index:
                target = name_index[nk]
                if target is None:
                    result.items.append(
                        BackfillPlanItem(
                            transcript_path=path,
                            managed_transcript_id=resolved.managed_transcript_id,
                            local_speaker_key=local_key,
                            display_name=display,
                            action="skip_ambiguous_name",
                            detail=(
                                "multiple active profiles share this display name; "
                                "link or merge manually"
                            ),
                        )
                    )
                    continue
                result.items.append(
                    BackfillPlanItem(
                        transcript_path=path,
                        managed_transcript_id=resolved.managed_transcript_id,
                        local_speaker_key=local_key,
                        display_name=display,
                        action="link",
                        target_profile_id=target,
                    )
                )
                continue

            # Reserve this name for subsequent transcripts in this plan.
            provisional_id = f"pending:{uuid4()}"
            if merge_by_name:
                name_index[nk] = provisional_id
            result.items.append(
                BackfillPlanItem(
                    transcript_path=path,
                    managed_transcript_id=resolved.managed_transcript_id,
                    local_speaker_key=local_key,
                    display_name=display,
                    action="create",
                    target_profile_id=provisional_id,
                )
            )

    return result


def _idempotency_key(action: str, managed_transcript_id: str, local_key: str) -> str:
    return f"backfill_from_maps.v1:{action}:{managed_transcript_id}:{local_key}"


def apply_backfill_plan(
    plan: BackfillResult,
    *,
    service: SpeakerProfileService | None = None,
    actor: str = "backfill_from_maps",
) -> BackfillResult:
    """Execute create/link items from a plan. Mutates profile store."""
    svc = service or SpeakerProfileService()
    # Map provisional pending:* ids → real profile_ids as creates commit.
    pending_to_real: dict[str, str] = {}
    out = BackfillResult(items=list(plan.items))

    for item in plan.items:
        if item.action not in ("create", "link"):
            continue
        assert item.managed_transcript_id is not None

        try:
            if item.action == "create":
                mutation = svc.create_profile_and_link(
                    operation_idempotency_key=_idempotency_key(
                        "create",
                        item.managed_transcript_id,
                        item.local_speaker_key,
                    ),
                    display_name=item.display_name,
                    managed_transcript_id=item.managed_transcript_id,
                    local_speaker_key=item.local_speaker_key,
                    created_by=actor,
                )
                profile_id = mutation.profile_id
                if not profile_id:
                    key = link_file_key(
                        item.managed_transcript_id, item.local_speaker_key
                    )
                    live = svc.get_live_link(key)
                    profile_id = live.profile_id if live else None
                if not profile_id:
                    raise SpeakerProfileContractError(
                        "create_profile_and_link did not yield a profile_id"
                    )
                if item.target_profile_id and item.target_profile_id.startswith(
                    "pending:"
                ):
                    pending_to_real[item.target_profile_id] = str(profile_id)
                applied = BackfillPlanItem(
                    transcript_path=item.transcript_path,
                    managed_transcript_id=item.managed_transcript_id,
                    local_speaker_key=item.local_speaker_key,
                    display_name=item.display_name,
                    action="create",
                    target_profile_id=str(profile_id),
                )
                out.applied.append(applied)
            else:
                target = item.target_profile_id
                if target and target.startswith("pending:"):
                    target = pending_to_real.get(target)
                if not target:
                    raise SpeakerProfileContractError(
                        f"missing target profile for link of "
                        f"{item.managed_transcript_id}/{item.local_speaker_key}"
                    )
                svc.link_existing_profile(
                    operation_idempotency_key=_idempotency_key(
                        "link",
                        item.managed_transcript_id,
                        item.local_speaker_key,
                    ),
                    managed_transcript_id=item.managed_transcript_id,
                    local_speaker_key=item.local_speaker_key,
                    profile_id=str(target),
                    actor=actor,
                )
                out.applied.append(
                    BackfillPlanItem(
                        transcript_path=item.transcript_path,
                        managed_transcript_id=item.managed_transcript_id,
                        local_speaker_key=item.local_speaker_key,
                        display_name=item.display_name,
                        action="link",
                        target_profile_id=str(target),
                    )
                )
        except Exception as exc:
            err = BackfillPlanItem(
                transcript_path=item.transcript_path,
                managed_transcript_id=item.managed_transcript_id,
                local_speaker_key=item.local_speaker_key,
                display_name=item.display_name,
                action="error",
                target_profile_id=item.target_profile_id,
                detail=str(exc),
            )
            out.errors.append(err)

    return out


def run_backfill_from_maps(
    *,
    apply: bool = False,
    merge_by_name: bool = True,
    exclude_names: set[str] | frozenset[str] | None = None,
    require_named_speaker: bool = True,
    service: SpeakerProfileService | None = None,
    actor: str = "backfill_from_maps",
) -> BackfillResult:
    """Plan (and optionally apply) a full managed-library backfill."""
    svc = service or SpeakerProfileService()
    plan = plan_backfill_from_maps(
        service=svc,
        merge_by_name=merge_by_name,
        exclude_names=exclude_names,
        require_named_speaker=require_named_speaker,
    )
    if not apply:
        return plan
    applied = apply_backfill_plan(plan, service=svc, actor=actor)
    # Preserve full plan inventory plus apply outcomes.
    return BackfillResult(
        items=plan.items,
        applied=applied.applied,
        errors=applied.errors,
    )
