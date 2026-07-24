"""Shared analyze pipeline for categorized lexicon marker modules."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.lexicon_markers import (
    ALGORITHM_VERSION,
    TOKENIZER_VERSION,
    aggregate_rates,
    count_tokens,
    is_english_supported,
    load_package_lexicon,
    match_phrases_in_text,
    resolve_transcript_language,
)
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.utils.text_utils import is_turn_taking_speaker_label


def run_marker_analysis(
    segments: Sequence[Mapping[str, Any]],
    *,
    module: str,
    lexicon_filename: str,
    categories: Sequence[str],
    schema_id: str,
    semantics_version: str,
    enabled_categories: Sequence[str] | None,
    min_tokens_for_rates: int,
    derive_fn: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    lang_code, lang_tag = resolve_transcript_language(segments, metadata)
    english_ok = is_english_supported(lang_code)

    exclusions = {
        "skipped_segments": 0,
        "skipped_reasons": {
            "no_speaker": 0,
            "ineligible_speaker": 0,
            "unsupported_language": 0,
        },
        "eligible_segment_count": 0,
    }

    base_meta = {
        "schema_id": schema_id,
        "semantics_version": semantics_version,
        "algorithm_version": ALGORITHM_VERSION,
        "tokenizer_version": TOKENIZER_VERSION,
        "lexicon_filename": lexicon_filename,
        "language": lang_code,
        "language_resolution": lang_tag,
        "language_status": "supported" if english_ok else "unsupported",
        "min_tokens_for_rates": int(min_tokens_for_rates),
        "enabled_categories": (
            list(enabled_categories)
            if enabled_categories is not None
            else list(categories)
        ),
    }

    if not english_ok:
        exclusions["skipped_segments"] = len(segments)
        exclusions["skipped_reasons"]["unsupported_language"] = len(segments)
        empty_counts = {c: 0 for c in categories}
        empty_stats = {
            "token_count": 0,
            "total_marker_hits": 0,
            "category_counts": empty_counts,
            "hits_per_100_tokens": None,
            "category_rates_per_100_tokens": {c: None for c in categories},
        }
        derived = derive_fn(empty_stats) if derive_fn else {}
        return {
            "usable": False,
            "metadata": base_meta,
            "hits": [],
            "speaker_stats": {},
            "global_stats": {**empty_stats, **derived},
            "exclusions": exclusions,
            "segments": list(segments),
        }

    from transcriptx.core.analysis.lexicon_markers import iter_phrases

    lexicon = load_package_lexicon(lexicon_filename)
    phrases = iter_phrases(lexicon, enabled_categories)

    token_counts: dict[str, int] = defaultdict(int)
    hits = []
    for index, seg in enumerate(segments):
        if not isinstance(seg, Mapping):
            exclusions["skipped_segments"] += 1
            exclusions["skipped_reasons"]["no_speaker"] += 1
            continue
        info = extract_speaker_info(seg)
        if info is not None:
            grouping_key = info.grouping_key
        else:
            label = seg.get("speaker")
            grouping_key = str(label) if label else None
        if grouping_key is None:
            exclusions["skipped_segments"] += 1
            exclusions["skipped_reasons"]["no_speaker"] += 1
            continue
        display = get_speaker_display_name(grouping_key, [seg], list(segments))
        if not display or not is_turn_taking_speaker_label(display):
            exclusions["skipped_segments"] += 1
            exclusions["skipped_reasons"]["ineligible_speaker"] += 1
            continue
        text = str(seg.get("text", "") or "")
        token_counts[display] += count_tokens(text)
        exclusions["eligible_segment_count"] += 1
        hits.extend(
            match_phrases_in_text(
                text,
                phrases,
                speaker=display,
                segment_index=index,
                module=module,
            )
        )

    global_stats, speaker_stats = aggregate_rates(
        hits,
        token_counts,
        categories,
        min_tokens_for_rates=min_tokens_for_rates,
    )
    derived = derive_fn(global_stats) if derive_fn else {}
    for speaker, stats in speaker_stats.items():
        speaker_derived = derive_fn(stats) if derive_fn else {}
        speaker_stats[speaker] = {**stats, **speaker_derived}

    return {
        "usable": True,
        "metadata": base_meta,
        "hits": [h.as_dict() for h in hits],
        "speaker_stats": speaker_stats,
        "global_stats": {**global_stats, **derived},
        "exclusions": exclusions,
        "segments": list(segments),
    }
