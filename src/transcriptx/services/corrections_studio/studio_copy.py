"""Pure helpers for Corrections Studio UI copy (testable without Streamlit)."""

from __future__ import annotations

from typing import List, Optional

from transcriptx.services.corrections_studio.schema import (
    CandidateGenerationDiagnostics,
    FuzzySkippedReason,
)


def stale_generation_banner_lines(
    *,
    generation_id: Optional[int],
    completed_at: Optional[str],
    detector_version: Optional[str],
) -> List[str]:
    lines = [
        "This candidate generation may be **out of date** relative to the current "
        "transcript, speaker map, correction config, memory rules, or session rules."
    ]
    if generation_id is not None:
        lines.append(
            f"Generation **#{generation_id}** (completed {completed_at or 'unknown'})."
        )
    if detector_version:
        lines.append(f"Stored detector version: `{detector_version}`.")
    lines.append("Click **Regenerate Candidates** to refresh with current settings.")
    return lines


def incompatible_transcript_banner_text() -> str:
    return (
        "The transcript file no longer matches this session's recorded fingerprint. "
        "Start a new session or restore the original transcript before regenerating."
    )


def low_or_zero_candidate_hints(
    diagnostics: Optional[CandidateGenerationDiagnostics],
) -> List[str]:
    """Explanations when the unfiltered candidate list is small or empty."""
    base = [
        "Corrections Studio only suggests **detector-based** fixes (memory hits, "
        "configured acronyms/phrases, strict consistency, and optional fuzzy speaker-name "
        "matches). It does not run broad spellcheck or grammar.",
        "An **empty Kind** filter means **all kinds** — it does not hide results.",
    ]
    if not diagnostics:
        base.append(
            "Regenerate after updating correction config, speaker maps, or reusable memory rules."
        )
        return base

    d = diagnostics
    base.append(
        f"Last generation: **{d.total_after_dedupe}** candidates after dedupe "
        f"({d.total_pre_dedupe} raw across detectors)."
    )

    pk = d.post_dedupe_counts_by_kind
    if (
        d.total_after_dedupe > 0
        and pk.consistency > 0
        and pk.memory_hit == 0
        and pk.acronym == 0
        and pk.fuzzy == 0
    ):
        base.append(
            "All current suggestions are **consistency**-based (same token appearing in multiple forms)."
        )

    if d.fuzzy_enabled:
        if d.fuzzy_skipped_reason == FuzzySkippedReason.no_speaker_map:
            base.append(
                "**Fuzzy** is on, but no speaker map could be loaded for this transcript — "
                "add or fix the sidecar map to enable name matching."
            )
        elif d.fuzzy_skipped_reason == FuzzySkippedReason.zero_map_entries:
            base.append(
                "**Fuzzy** is on, but the speaker map is empty — assign display names in the map."
            )
        elif d.fuzzy_skipped_reason == FuzzySkippedReason.zero_named_speakers:
            base.append(
                "**Fuzzy** is on, but no **named** speakers remain in the map vocabulary after "
                "filtering placeholders — resolve diarized IDs to real names in the map."
            )
        elif d.fuzzy_named_speaker_count > 0:
            base.append(
                f"Fuzzy vocabulary: **{d.fuzzy_named_speaker_count}** named speaker(s) from the map."
            )

    if d.known_acronym_count == 0 and d.known_org_phrase_count == 0:
        base.append(
            "Acronym/org detectors only use **configured** lists — expand them in analysis "
            "correction settings if needed."
        )

    if d.total_after_dedupe == 0:
        base.extend(
            [
                "**Next steps:** regenerate after config or rule changes; expand known acronyms/org phrases; "
                "add reusable memory rules; enable/configure fuzzy once speaker maps name real people.",
            ]
        )

    return base
