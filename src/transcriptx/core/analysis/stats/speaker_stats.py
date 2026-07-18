"""Stats analysis module."""

from transcriptx.utils.text_utils import is_eligible_named_speaker

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.segment_duration import compute_eligible_speaker_durations
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
    duration_result = compute_eligible_speaker_durations(
        segments,
        ignored_ids=ignored_ids,
        grouped_hint=grouped or None,
    )
    speaker_segments_map = duration_result.speaker_segments
    speaker_key_map = duration_result.speaker_key_map
    allow_fallback_speakers = duration_result.allow_fallback_speakers

    stats = []
    sentiment_summary = {}

    if tic_list is None:
        tic_list = []

    for name, texts in grouped.items():
        speaker_key = speaker_key_map.get(name, name)
        if not allow_fallback_speakers and not is_eligible_named_speaker(
            name, speaker_key, ignored_ids or set()
        ):
            continue

        word_count = sum(len(t.split()) for t in texts)

        speaker_segs = speaker_segments_map.get(name, [])
        segment_count = len(speaker_segs)
        duration = float(duration_result.durations.get(name, 0.0))

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
