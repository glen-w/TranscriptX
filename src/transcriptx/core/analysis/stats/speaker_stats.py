"""Stats analysis module."""

from transcriptx.utils.text_utils import is_eligible_named_speaker

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.analysis.sentiment import score_sentiment

logger = get_logger()


def compute_speaker_stats(
    grouped: dict,
    segments: list,
    speaker_map: dict = None,
    tic_list: list = None,
    ignored_ids: set[str] | None = None,
):
    """
    Computes per-speaker metrics including word count, tic rate, segment count, duration, etc.

    Args:
        grouped: Dictionary mapping speaker display name to list of text strings
        segments: List of all transcript segments
        speaker_map: Deprecated speaker mapping (kept for backward compatibility, not used)
        tic_list: List of verbal tics to count

    Returns:
        Tuple of (stats_list, sentiment_summary_dict)
    """
    from transcriptx.core.utils.speaker_extraction import (
        group_segments_by_speaker,
        get_speaker_display_name,
    )

    # Group segments by speaker using database-driven approach
    grouped_segments = group_segments_by_speaker(segments)

    # Create mapping from display name to grouped segments
    speaker_segments_map = {}
    speaker_key_map: dict[str, str] = {}
    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if display_name and is_eligible_named_speaker(
            display_name, str(grouping_key), ignored_ids or set()
        ):
            speaker_segments_map[display_name] = segs
            speaker_key_map[display_name] = str(grouping_key)

    stats = []
    sentiment_summary = {}

    if tic_list is None:
        tic_list = []

    for name, texts in grouped.items():
        speaker_key = speaker_key_map.get(name, name)
        if not is_eligible_named_speaker(name, speaker_key, ignored_ids or set()):
            continue

        word_count = sum(len(t.split()) for t in texts)

        # Get segments for this speaker from grouped segments
        speaker_segs = speaker_segments_map.get(name, [])
        segment_count = len(speaker_segs)
        duration = sum(seg.get("end", 0) - seg.get("start", 0) for seg in speaker_segs)

        tic_count = sum(1 for t in " ".join(texts).lower().split() if t in tic_list)
        avg_segment_len = word_count / segment_count if segment_count else 0
        tic_rate = tic_count / word_count if word_count else 0

        stats.append(
            (duration, name, word_count, segment_count, tic_rate, avg_segment_len)
        )

        scores = [score_sentiment(t) for t in texts]
        agg = {
            "compound": (
                sum(s["compound"] for s in scores) / len(scores) if scores else 0
            ),
            "pos": sum(s["pos"] for s in scores) / len(scores) if scores else 0,
            "neu": sum(s["neu"] for s in scores) / len(scores) if scores else 0,
            "neg": sum(s["neg"] for s in scores) / len(scores) if scores else 0,
        }
        sentiment_summary[name] = agg

    stats.sort(reverse=True)
    return stats, sentiment_summary
