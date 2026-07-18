"""Centralized segment source-identity policy for emotion-family modules."""

from __future__ import annotations

from typing import Any, MutableMapping, Sequence

SOURCE_IDENTITY_POLICY_V1 = "emotion_family_source_identity_v1"


def ensure_segment_ids(
    segments: Sequence[MutableMapping[str, Any]],
    *,
    mint_missing: bool = True,
) -> list[str]:
    """
    Ensure every segment has a unique non-empty id.

    Migration policy (v1): when both ``id`` and ``segment_id`` are missing,
    mint ``seg-{index}`` in place. Duplicate non-empty ids raise ValueError.
    Individual modules must not invent ids independently.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for i, seg in enumerate(segments):
        sid = seg.get("id") or seg.get("segment_id")
        if sid is None or not str(sid).strip():
            if not mint_missing:
                raise ValueError(
                    f"segment_id missing at index {i}; "
                    f"policy={SOURCE_IDENTITY_POLICY_V1}"
                )
            sid = f"seg-{i}"
            seg["id"] = sid
        sid_s = str(sid)
        if sid_s in seen:
            raise ValueError(f"duplicate segment_id: {sid_s}")
        seen.add(sid_s)
        ordered.append(sid_s)
    return ordered
