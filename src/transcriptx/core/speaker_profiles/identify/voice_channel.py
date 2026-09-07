"""Voice channel: strong unique ECAPA suggestions (no enrol)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate
from transcriptx.core.speaker_profiles.voice.match_service import SpeakerMatchService
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def _keyed_segments(
    segments: Sequence[Mapping[str, Any]], local_speaker_key: str
) -> list[dict[str, Any]]:
    key = normalize_diarized_id(local_speaker_key)
    out: list[dict[str, Any]] = []
    for segment in segments:
        raw = segment.get("speaker_diarized_id")
        if raw is None or str(raw).strip() == "":
            raw = segment.get("speaker")
        if normalize_diarized_id(raw) == key:
            out.append(dict(segment))
    return out


def analyse_voice_candidates(
    *,
    managed_transcript_id: str,
    transcript_path: Path,
    segments: Sequence[Mapping[str, Any]],
    speaker_ids: Sequence[str],
    match_service: SpeakerMatchService | None = None,
    root: Path | None = None,
) -> dict[str, ChannelCandidate]:
    """Return strong unique voice candidates; abstain on errors or weak scores."""
    service = match_service or SpeakerMatchService(root=root)
    out: dict[str, ChannelCandidate] = {}
    all_segments = [dict(s) for s in segments]
    for raw_id in speaker_ids:
        key = normalize_diarized_id(raw_id)
        if not key:
            continue
        keyed = _keyed_segments(all_segments, key)
        if not keyed:
            continue
        fingerprint = compute_occurrence_fingerprint(keyed)
        try:
            result = service.analyse_occurrence(
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=key,
                transcript_path=Path(transcript_path),
                segments=all_segments,
                occurrence_fingerprint=fingerprint,
                require_activation=True,
            )
        except Exception:
            continue
        if result.outcome != "SuggestionAvailable":
            continue
        ui = list(result.candidates_ui or ())
        if not ui:
            continue
        best = ui[0]
        if str(best.get("confidence") or "") != "strong":
            continue
        if len(ui) > 1 and str(ui[1].get("confidence") or "") == "strong":
            continue
        display = str(best.get("display_name") or "").strip()
        profile_id = str(best.get("profile_id") or "").strip()
        if not display or not profile_id:
            continue
        out[key] = ChannelCandidate(
            channel="voice",
            display_name=display,
            profile_id=profile_id,
            score=(
                float(best["score_diagnostic"])
                if best.get("score_diagnostic") is not None
                else None
            ),
            confidence="strong",
            evidence={"outcome": result.outcome},
            suggestion_id=result.suggestion_id,
            suggestion_digest=result.suggestion_digest,
            model_generation_id=result.model_generation_id,
        )
    return out
