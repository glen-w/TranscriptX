"""Segment work-item construction for emotion-family producers.

Internal submodule — import directly; not part of ``emotion_family.__all__``.

Callers must run ``ensure_segment_ids`` first. This helper never mints,
rewrites, or reconciles IDs. It does not decide classifier or lexical score
eligibility, and has no cache/model/scoring/projection/aggregation/
persistence/logging/result-shape responsibilities.

Lexical cache asymmetry (preserved; do not “fix” under helper adoption):
``needed_sids`` for lexical inference cache is computed by the producer from
segments *before* this helper runs. Unsupported-language rows are not stored
in the lexical inference cache, so mixed-language transcripts may be unable
to cache-hit. See emotion extract locked spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping, Sequence

from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash
from transcriptx.core.analysis.emotion_family.language import (
    extract_transcript_metadata,
    resolve_segment_language,
)
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)


@dataclass(frozen=True)
class SegmentWorkItem:
    """Immutable snapshot fields plus the original mutable segment object."""

    seg: MutableMapping[str, Any]
    sid: str
    speaker: str
    lang: str | None
    lang_res: str
    text: str
    text_hash: str


def build_segment_work_items(
    segments: Sequence[MutableMapping[str, Any]],
) -> tuple[tuple[SegmentWorkItem, ...], int]:
    """
    Build work items in input order.

    Returns ``(work_items, assumed_en_missing_metadata_count)``.

    Canonical id extraction matches producers::

        raw_sid = seg.get("id") or seg.get("segment_id")
        if raw_sid is None or not str(raw_sid).strip():
            raise ValueError(...)
        sid = str(raw_sid)  # not strip-normalised
    """
    meta = extract_transcript_metadata(segments)
    assumed_en = 0
    items: list[SegmentWorkItem] = []
    for seg in segments:
        raw_sid = seg.get("id") or seg.get("segment_id")
        if raw_sid is None or not str(raw_sid).strip():
            raise ValueError(
                "segment missing non-empty canonical id after ensure_segment_ids"
            )
        sid = str(raw_sid)

        speaker_info = extract_speaker_info(seg)
        speaker = ""
        if speaker_info is not None:
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )

        lang, lang_res = resolve_segment_language(seg, meta)
        if lang_res == "assumed_en_missing_metadata":
            assumed_en += 1

        text = (seg.get("text") or "").strip()
        text_hash = segment_text_hash(seg.get("text"))
        items.append(
            SegmentWorkItem(
                seg=seg,
                sid=sid,
                speaker=speaker,
                lang=lang,
                lang_res=lang_res,
                text=text,
                text_hash=text_hash,
            )
        )
    return tuple(items), assumed_en
