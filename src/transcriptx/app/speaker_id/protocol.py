"""Revisioned command / acknowledgement envelopes for Speaker ID actions."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Sequence

PROTOCOL_VERSION = "1"

SpeakerIdActionName = Literal[
    "save_name",
    "ignore_toggle",
    "navigate_prev",
    "navigate_next",
    "navigate_jump",
]

SpeakerIdAckStatus = Literal[
    "ok",
    "partial",
    "rejected_stale",
    "rejected_protocol",
    "error",
]


@dataclass(frozen=True)
class SpeakerIdFlash:
    """User-facing one-shot message."""

    level: Literal["info", "warning", "error", "success"]
    message: str


@dataclass(frozen=True)
class SpeakerIdEffects:
    """UI effects to apply after a command acknowledgement.

    Streamlit-agnostic: adapters apply these to session state / CCv2 data.
    """

    flashes: tuple[SpeakerIdFlash, ...] = ()
    navigate_to_idx: Optional[int] = None
    sync_jump: bool = False
    invalidate_summary_sig: Optional[tuple[int, int, int]] = None
    requires_app_rerun: bool = False
    cache_invalidation_signal: Any = None


@dataclass(frozen=True)
class SpeakerIdCommand:
    """Revisioned domain command envelope."""

    action: SpeakerIdActionName
    transcript_id: str
    action_id: str
    action_seq: int
    current_speaker_idx: int
    protocol_version: str = PROTOCOL_VERSION
    frontend_build_id: str = "legacy"
    expected_speaker_id: Optional[str] = None
    expected_mapping_revision: Optional[str] = None
    transcript_revision: Optional[str] = None
    audio_fingerprint: Optional[str] = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeakerIdAck:
    """Authoritative acknowledgement for a Speaker ID command."""

    action_id: str
    action_seq: int
    status: SpeakerIdAckStatus
    transcript_id: str
    message: Optional[str] = None
    transcript_revision: Optional[str] = None
    mapping_revision: Optional[str] = None
    active_speaker_id: Optional[str] = None
    active_speaker_idx: Optional[int] = None
    speaker_map: Mapping[str, str] = field(default_factory=dict)
    ignored_speakers: Sequence[str] = ()
    effects: SpeakerIdEffects = field(default_factory=SpeakerIdEffects)


def new_action_id() -> str:
    return uuid.uuid4().hex


def transcript_revision_from_path(transcript_path: str | Path) -> str:
    """Stable revision token from transcript file identity (mtime_ns + size)."""
    path = Path(transcript_path)
    try:
        st = path.stat()
        raw = f"{int(st.st_mtime_ns)}:{int(st.st_size)}"
    except OSError:
        raw = "missing"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def mapping_revision_from_sidecar(transcript_path: str | Path) -> str:
    """Revision token from speaker-map sidecar mtime (0 when absent)."""
    try:
        from transcriptx.io.speaker_map_resolver import speaker_map_sidecar_candidates

        for candidate in speaker_map_sidecar_candidates(Path(transcript_path)):
            try:
                mtime_ns = int(candidate.stat().st_mtime_ns)
                return hashlib.sha1(f"sidecar:{mtime_ns}".encode("utf-8")).hexdigest()[
                    :16
                ]
            except OSError:
                continue
    except Exception:
        pass
    return hashlib.sha1(b"sidecar:0").hexdigest()[:16]


def mapping_revision_from_state(
    speaker_map: Mapping[str, str] | None,
    ignored_speakers: Sequence[str] | None,
) -> str:
    """Content hash of mapping facts (used after mutations when mtime may lag)."""
    items = sorted((str(k), str(v)) for k, v in (speaker_map or {}).items())
    ignored = sorted(str(s) for s in (ignored_speakers or []) if s is not None)
    raw = repr((items, ignored)).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
