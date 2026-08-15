"""SpeakerIdActionService — shared mutation orchestration for Speaker ID."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional, Sequence

from transcriptx.app.speaker_id.protocol import (
    PROTOCOL_VERSION,
    SpeakerIdAck,
    SpeakerIdCommand,
    SpeakerIdEffects,
    SpeakerIdFlash,
    mapping_revision_from_sidecar,
    mapping_revision_from_state,
    transcript_revision_from_path,
)
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController


def _speaker_map_display_name(speaker_map: dict, sid: str) -> str:
    nid = normalize_diarized_id(sid)
    if nid:
        v = speaker_map.get(nid)
        if is_effective_speaker_name(nid, v):
            return str(v).strip()
    v = speaker_map.get(sid)
    if is_effective_speaker_name(sid, v):
        return str(v).strip()
    return ""


def _is_speaker_ignored(ignored: Sequence[str], sid: str) -> bool:
    nid = normalize_diarized_id(sid)
    if not nid and not sid:
        return False
    for ig in ignored or []:
        if ig is None or not str(ig).strip():
            continue
        raw = str(ig).strip()
        if sid == raw or (nid and nid == raw):
            return True
        if nid and normalize_diarized_id(raw) == nid:
            return True
    return False


def remaining_count(
    speaker_ids: Sequence[str],
    speaker_map: dict,
    ignored: Sequence[str],
) -> tuple[int, int, int]:
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = len(speaker_ids) - named - n_ignored
    return named, n_ignored, remaining


def next_unnamed_idx(
    speaker_ids: Sequence[str],
    speaker_map: dict,
    ignored: Sequence[str],
    current: int,
) -> int:
    """Advance to the next unnamed, non-ignored speaker after a successful mutation."""
    ids = list(speaker_ids)
    if 0 <= current < len(ids):
        sid = ids[current]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return current
    for i in range(current + 1, len(ids)):
        sid = ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    for i in range(0, current):
        sid = ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    return current


IndexLoader = Callable[[str], object]


class SpeakerIdActionService:
    """Execute revisioned Speaker ID commands against domain services.

    Idempotent on ``action_id`` (process-local LRU). Does not touch Streamlit.
    """

    _IDEMPOTENCY_MAX = 256

    def __init__(
        self,
        controller: SpeakerStudioController,
        *,
        index_loader: Optional[IndexLoader] = None,
        profile_context_resolver: Optional[Callable[[str], object]] = None,
        expected_frontend_build_ids: Optional[Sequence[str]] = None,
    ) -> None:
        self._controller = controller
        self._index_loader = index_loader or self._default_index_loader
        self._profile_context_resolver = profile_context_resolver
        self._expected_builds = set(expected_frontend_build_ids or ("legacy",))
        self._acks: OrderedDict[str, SpeakerIdAck] = OrderedDict()

    @staticmethod
    def _default_index_loader(transcript_path: str):
        from transcriptx.web.cache_helpers import load_speaker_identification_index

        return load_speaker_identification_index(transcript_path)

    def execute(self, command: SpeakerIdCommand) -> SpeakerIdAck:
        prior = self._acks.get(command.action_id)
        if prior is not None:
            return prior

        ack = self._execute_once(command)
        self._acks[command.action_id] = ack
        while len(self._acks) > self._IDEMPOTENCY_MAX:
            self._acks.popitem(last=False)
        return ack

    def _execute_once(self, command: SpeakerIdCommand) -> SpeakerIdAck:
        if command.protocol_version != PROTOCOL_VERSION:
            return self._reject(
                command,
                status="rejected_protocol",
                message=(
                    f"Protocol mismatch: got {command.protocol_version!r}, "
                    f"expected {PROTOCOL_VERSION!r}. Reload the workspace."
                ),
            )
        if (
            self._expected_builds
            and command.frontend_build_id not in self._expected_builds
            and command.frontend_build_id != "legacy"
        ):
            # Allow "legacy" always; CCv2 builds must be listed when configured.
            return self._reject(
                command,
                status="rejected_protocol",
                message=(
                    f"Frontend build mismatch: {command.frontend_build_id!r}. "
                    "Reload or fall back to the classic Speaker ID UI."
                ),
            )

        path = str(command.transcript_id)
        try:
            index = self._index_loader(path)
        except FileNotFoundError:
            return self._reject(
                command,
                status="error",
                message="Transcript file is missing.",
            )

        speaker_ids = list(getattr(index, "ordered_speaker_ids", ()) or ())
        if not speaker_ids:
            return self._reject(
                command,
                status="error",
                message="No speakers found.",
            )

        idx = command.current_speaker_idx
        if idx < 0 or idx >= len(speaker_ids):
            idx = 0
        active_id = speaker_ids[idx]

        if (
            command.expected_speaker_id is not None
            and active_id != command.expected_speaker_id
        ):
            return self._reject(
                command,
                status="rejected_stale",
                message="Active speaker changed; action was not applied. Try again.",
                speaker_ids=speaker_ids,
                active_idx=idx,
                active_id=active_id,
            )

        if command.transcript_revision is not None:
            current_tx = transcript_revision_from_path(path)
            if command.transcript_revision != current_tx:
                return self._reject(
                    command,
                    status="rejected_stale",
                    message="Transcript changed underfoot; action was not applied.",
                    speaker_ids=speaker_ids,
                    active_idx=idx,
                    active_id=active_id,
                )

        if command.expected_mapping_revision is not None:
            current_map_rev = mapping_revision_from_sidecar(path)
            # Also accept content-hash form when sidecar mtime unchanged but
            # callers supplied a post-mutation content revision.
            map_state = self._controller.get_mapping_status(path)
            content_rev = mapping_revision_from_state(
                map_state.speaker_map, map_state.ignored_speakers
            )
            if command.expected_mapping_revision not in (
                current_map_rev,
                content_rev,
            ):
                return self._reject(
                    command,
                    status="rejected_stale",
                    message="Speaker map changed underfoot; action was not applied.",
                    speaker_ids=speaker_ids,
                    active_idx=idx,
                    active_id=active_id,
                    speaker_map=dict(map_state.speaker_map or {}),
                    ignored=list(map_state.ignored_speakers or []),
                )

        try:
            Path(path).resolve(strict=False)
        except OSError:
            pass

        if command.action == "save_name":
            return self._save_name(command, path, speaker_ids, idx, active_id)
        if command.action == "ignore_toggle":
            return self._ignore_toggle(command, path, speaker_ids, idx, active_id)
        if command.action == "navigate_prev":
            return self._navigate(command, path, speaker_ids, idx, active_id, delta=-1)
        if command.action == "navigate_next":
            return self._navigate(command, path, speaker_ids, idx, active_id, delta=1)
        if command.action == "navigate_jump":
            target = int(command.payload.get("target_idx", idx))
            return self._navigate_jump(command, path, speaker_ids, target)
        return self._reject(
            command,
            status="error",
            message=f"Unknown action: {command.action!r}",
            speaker_ids=speaker_ids,
            active_idx=idx,
            active_id=active_id,
        )

    def _save_name(
        self,
        command: SpeakerIdCommand,
        path: str,
        speaker_ids: list[str],
        speaker_idx: int,
        active_id: str,
    ) -> SpeakerIdAck:
        name = str(command.payload.get("display_name") or "").strip()
        if not name:
            return self._reject(
                command,
                status="error",
                message="Enter a name before saving.",
                speaker_ids=speaker_ids,
                active_idx=speaker_idx,
                active_id=active_id,
                flash_level="warning",
            )

        link_profile = bool(command.payload.get("link_profile", False))
        summary_sig = self._summary_sig(path)
        flashes: list[SpeakerIdFlash] = []
        cache_signal = None
        status: str = "ok"

        try:
            profile_managed = False
            if self._profile_context_resolver is not None:
                ctx = self._profile_context_resolver(path)
                profile_managed = bool(getattr(ctx, "is_managed", False))
            else:
                profile_managed = self._default_is_managed(path)

            if link_profile and profile_managed:
                from transcriptx.services.speaker_profiles.create_and_name import (
                    create_profile_link_and_name,
                )

                partial = create_profile_link_and_name(
                    transcript_path=path,
                    raw_speaker=active_id,
                    display_name=name,
                    controller=self._controller,
                    create_profile=True,
                    apply_sidecar_name=True,
                    method="web",
                )
                cache_signal = getattr(partial, "effective_signal", None)
                if getattr(partial, "is_partial", False):
                    status = "partial"
                    flashes.append(
                        SpeakerIdFlash(
                            level="warning",
                            message=(
                                "Profile link saved, but local naming failed: "
                                f"{getattr(partial, 'naming_error', '')}"
                            ),
                        )
                    )
                new_state = self._controller.get_mapping_status(path)
            else:
                new_state = self._controller.apply_mapping_mutation(
                    path, active_id, name, method="web"
                )
        except Exception as exc:
            return self._reject(
                command,
                status="error",
                message=str(exc),
                speaker_ids=speaker_ids,
                active_idx=speaker_idx,
                active_id=active_id,
            )

        return self._ack_after_mutation(
            command,
            path=path,
            speaker_ids=speaker_ids,
            speaker_idx=speaker_idx,
            new_state=new_state,
            summary_sig=summary_sig,
            status=status,  # type: ignore[arg-type]
            flashes=flashes,
            cache_signal=cache_signal,
        )

    def _ignore_toggle(
        self,
        command: SpeakerIdCommand,
        path: str,
        speaker_ids: list[str],
        speaker_idx: int,
        active_id: str,
    ) -> SpeakerIdAck:
        summary_sig = self._summary_sig(path)
        try:
            map_state = self._controller.get_mapping_status(path)
            ignored = list(getattr(map_state, "ignored_speakers", None) or [])
            if _is_speaker_ignored(ignored, active_id):
                new_state = self._controller.unignore_speaker(
                    path, active_id, method="web"
                )
            else:
                new_state = self._controller.ignore_speaker(
                    path, active_id, method="web"
                )
        except Exception as exc:
            return self._reject(
                command,
                status="error",
                message=str(exc),
                speaker_ids=speaker_ids,
                active_idx=speaker_idx,
                active_id=active_id,
            )
        return self._ack_after_mutation(
            command,
            path=path,
            speaker_ids=speaker_ids,
            speaker_idx=speaker_idx,
            new_state=new_state,
            summary_sig=summary_sig,
            status="ok",
            flashes=[],
            cache_signal=None,
        )

    def _navigate(
        self,
        command: SpeakerIdCommand,
        path: str,
        speaker_ids: list[str],
        speaker_idx: int,
        active_id: str,
        *,
        delta: int,
    ) -> SpeakerIdAck:
        target = speaker_idx + delta
        if target < 0 or target >= len(speaker_ids):
            map_state = self._controller.get_mapping_status(path)
            return SpeakerIdAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="ok",
                transcript_id=path,
                transcript_revision=transcript_revision_from_path(path),
                mapping_revision=mapping_revision_from_state(
                    map_state.speaker_map, map_state.ignored_speakers
                ),
                active_speaker_id=active_id,
                active_speaker_idx=speaker_idx,
                speaker_map=dict(map_state.speaker_map or {}),
                ignored_speakers=tuple(map_state.ignored_speakers or ()),
                effects=SpeakerIdEffects(),
            )
        return self._navigate_jump(command, path, speaker_ids, target)

    def _navigate_jump(
        self,
        command: SpeakerIdCommand,
        path: str,
        speaker_ids: list[str],
        target_idx: int,
    ) -> SpeakerIdAck:
        if target_idx < 0:
            target_idx = 0
        if target_idx >= len(speaker_ids):
            target_idx = len(speaker_ids) - 1
        map_state = self._controller.get_mapping_status(path)
        active_id = speaker_ids[target_idx]
        return SpeakerIdAck(
            action_id=command.action_id,
            action_seq=command.action_seq,
            status="ok",
            transcript_id=path,
            transcript_revision=transcript_revision_from_path(path),
            mapping_revision=mapping_revision_from_state(
                map_state.speaker_map, map_state.ignored_speakers
            ),
            active_speaker_id=active_id,
            active_speaker_idx=target_idx,
            speaker_map=dict(map_state.speaker_map or {}),
            ignored_speakers=tuple(map_state.ignored_speakers or ()),
            effects=SpeakerIdEffects(
                navigate_to_idx=target_idx,
                sync_jump=command.action != "navigate_jump",
            ),
        )

    def _ack_after_mutation(
        self,
        command: SpeakerIdCommand,
        *,
        path: str,
        speaker_ids: list[str],
        speaker_idx: int,
        new_state,
        summary_sig: tuple[int, int, int],
        status: str,
        flashes: list[SpeakerIdFlash],
        cache_signal,
    ) -> SpeakerIdAck:
        speaker_map = dict(new_state.speaker_map or {})
        ignored = list(new_state.ignored_speakers or [])
        next_idx = next_unnamed_idx(speaker_ids, speaker_map, ignored, speaker_idx)
        _, _, remaining = remaining_count(speaker_ids, speaker_map, ignored)
        requires_app_rerun = remaining == 0 and len(speaker_ids) > 0
        active_id = speaker_ids[next_idx] if speaker_ids else None
        return SpeakerIdAck(
            action_id=command.action_id,
            action_seq=command.action_seq,
            status=status,  # type: ignore[arg-type]
            transcript_id=path,
            transcript_revision=transcript_revision_from_path(path),
            mapping_revision=mapping_revision_from_state(speaker_map, ignored),
            active_speaker_id=active_id,
            active_speaker_idx=next_idx,
            speaker_map=speaker_map,
            ignored_speakers=tuple(ignored),
            effects=SpeakerIdEffects(
                flashes=tuple(flashes),
                navigate_to_idx=next_idx,
                sync_jump=True,
                invalidate_summary_sig=summary_sig,
                requires_app_rerun=requires_app_rerun,
                cache_invalidation_signal=cache_signal,
            ),
        )

    def _reject(
        self,
        command: SpeakerIdCommand,
        *,
        status: str,
        message: str,
        speaker_ids: Optional[list[str]] = None,
        active_idx: Optional[int] = None,
        active_id: Optional[str] = None,
        speaker_map: Optional[dict] = None,
        ignored: Optional[list] = None,
        flash_level: str = "warning",
    ) -> SpeakerIdAck:
        level = "error" if status == "error" and flash_level == "warning" else flash_level
        if status == "error" and flash_level == "warning" and message.startswith(
            "Enter a name"
        ):
            level = "warning"
        flash_level_lit: str = level if level in ("info", "warning", "error", "success") else "warning"
        return SpeakerIdAck(
            action_id=command.action_id,
            action_seq=command.action_seq,
            status=status,  # type: ignore[arg-type]
            transcript_id=str(command.transcript_id),
            message=message,
            transcript_revision=transcript_revision_from_path(command.transcript_id),
            mapping_revision=mapping_revision_from_state(speaker_map, ignored),
            active_speaker_id=active_id,
            active_speaker_idx=active_idx,
            speaker_map=dict(speaker_map or {}),
            ignored_speakers=tuple(ignored or ()),
            effects=SpeakerIdEffects(
                flashes=(
                    SpeakerIdFlash(level=flash_level_lit, message=message),  # type: ignore[arg-type]
                ),
            ),
        )

    @staticmethod
    def _summary_sig(path: str) -> tuple[int, int, int]:
        from transcriptx.web.cache_helpers import transcript_summary_signature

        return transcript_summary_signature(path)

    @staticmethod
    def _default_is_managed(path: str) -> bool:
        try:
            from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

            return ManagedTranscriptResolver().is_managed_path(path)
        except Exception:
            return False
