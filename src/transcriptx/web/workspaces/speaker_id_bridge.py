"""Assemble CCv2 Speaker ID workspace data + dispatch triggered commands."""

from __future__ import annotations

import base64
from typing import Any, Mapping, Optional, Sequence

from transcriptx.app.speaker_id import (
    PROTOCOL_VERSION,
    SpeakerIdActionService,
    SpeakerIdCommand,
    mapping_revision_from_state,
    transcript_revision_from_path,
)
from transcriptx.app.speaker_id.effects import apply_speaker_id_ack_effects
from transcriptx.web.workspaces.clip_transport import encode_clip_b64, within_clip_budget

try:
    from transcriptx_workspaces import FRONTEND_BUILD_ID
except Exception:  # pragma: no cover - package may be optional during import
    FRONTEND_BUILD_ID = "tx-workspaces-0.1.0"

# Prefetch budgets (docs/dev/theme_c_workspaces_ccv2.md)
MAX_CLIPS_PER_WARM = 8
MAX_BYTES_PER_CLIP = 1_500_000
MAX_BLOB_BYTES = 8_000_000


def stable_workspace_key(transcript_id: str) -> str:
    """Transcript-scoped CCv2 Python key (frontend identity)."""
    return f"speaker_id_ws:{transcript_id}"


def build_workspace_data(
    *,
    transcript_path: str,
    speaker_ids: Sequence[str],
    active_speaker_id: str,
    speaker_labels: Mapping[str, str],
    speaker_map: Mapping[str, str],
    ignored_speakers: Sequence[str],
    samples: Sequence[Mapping[str, Any]],
    controller,
    audio_path=None,
    link_profile_allowed: bool = False,
    draft_name: str = "",
    ui_status: str = "",
    last_ack: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build JSON-serialisable ``data=`` for the Speaker ID CCv2 component."""
    mapping_rev = mapping_revision_from_state(speaker_map, ignored_speakers)
    tx_rev = transcript_revision_from_path(transcript_path)
    speakers = []
    ignored = list(ignored_speakers or [])
    for sid in speaker_ids:
        speakers.append(
            {
                "id": sid,
                "label": speaker_labels.get(sid, sid),
                "named": bool(speaker_map.get(sid)),
                "ignored": sid in ignored,
            }
        )

    sample_rows: list[dict[str, Any]] = []
    for raw in list(samples)[:MAX_CLIPS_PER_WARM]:
        start = float(raw.get("start") or 0.0)
        end = float(raw.get("end") or 0.0)
        text = str(raw.get("text") or "")
        status = controller.cached_clip_status(
            transcript_path, start, end, audio_path=audio_path
        )
        clip_b64 = None
        if status.status == "hit":
            blob = controller.get_cached_clip_bytes(
                transcript_path, start, end, audio_path=audio_path
            )
            if blob and within_clip_budget(len(blob), MAX_BYTES_PER_CLIP):
                clip_b64 = encode_clip_b64(blob)
            elif blob:
                status_name = "too_large"
            else:
                status_name = status.status
        else:
            status_name = status.status
            if status.status == "miss":
                controller.enqueue_clip(
                    transcript_path, start, end, audio_path=audio_path
                )
                status_name = "pending"
        sample_rows.append(
            {
                "clip_id": status.clip_id or f"{start:.3f}-{end:.3f}",
                "start": start,
                "end": end,
                "text": text,
                "clip_b64": clip_b64,
                "clip_status": status_name if clip_b64 is None else "hit",
            }
        )

    return {
        "protocol_version": PROTOCOL_VERSION,
        "frontend_build_id": FRONTEND_BUILD_ID,
        "transcript_id": str(transcript_path),
        "transcript_revision": tx_rev,
        "mapping_revision": mapping_rev,
        "active_speaker_id": active_speaker_id,
        "speakers": speakers,
        "samples": sample_rows,
        "draft_name": draft_name,
        "link_profile_allowed": link_profile_allowed,
        "capabilities": {
            "ffmpeg": bool(controller.ffmpeg_available()),
            "profile_link": link_profile_allowed,
        },
        "ui": {"status": ui_status, "disabled": False},
        "ack": dict(last_ack) if last_ack else None,
        "budgets": {"max_blob_bytes": MAX_BLOB_BYTES},
    }


def dispatch_workspace_command(
    command: Mapping[str, Any] | None,
    *,
    service: SpeakerIdActionService,
    speaker_ids: Sequence[str],
    current_speaker_idx: int,
    apply_ack,
) -> Optional[dict[str, Any]]:
    """Validate + execute a frontend command envelope; apply ack via callback."""
    if not command:
        return None
    action = str(command.get("action") or "")
    if action == "protocol_mismatch":
        ack = {
            "action_id": command.get("action_id"),
            "action_seq": int(command.get("action_seq") or 0),
            "status": "rejected_protocol",
            "message": "Frontend/protocol mismatch — reload or use classic Speaker ID.",
        }
        return ack
    if action == "enqueue_clip":
        # Non-mutating: handled by data rebuild on next run; still ack.
        return {
            "action_id": command.get("action_id"),
            "action_seq": int(command.get("action_seq") or 0),
            "status": "ok",
            "message": None,
        }

    # Map navigate_jump by speaker id → index when provided.
    payload = dict(command.get("payload") or {})
    if action == "navigate_jump" and "target_speaker_id" in payload:
        target_id = payload["target_speaker_id"]
        try:
            payload["target_idx"] = list(speaker_ids).index(target_id)
        except ValueError:
            payload["target_idx"] = current_speaker_idx

    cmd = SpeakerIdCommand(
        action=action,  # type: ignore[arg-type]
        transcript_id=str(command.get("transcript_id") or ""),
        action_id=str(command.get("action_id") or ""),
        action_seq=int(command.get("action_seq") or 0),
        current_speaker_idx=current_speaker_idx,
        protocol_version=str(command.get("protocol_version") or ""),
        frontend_build_id=str(command.get("frontend_build_id") or ""),
        expected_speaker_id=command.get("expected_speaker_id"),
        expected_mapping_revision=command.get("expected_mapping_revision"),
        transcript_revision=command.get("transcript_revision"),
        audio_fingerprint=command.get("audio_fingerprint"),
        payload=payload,
    )
    # Accept this package's build id.
    service._expected_builds = {FRONTEND_BUILD_ID, "legacy"}
    ack = service.execute(cmd)
    apply_ack(ack)
    return {
        "action_id": ack.action_id,
        "action_seq": ack.action_seq,
        "status": ack.status,
        "message": ack.message,
    }
