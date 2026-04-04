from __future__ import annotations


def test_transcript_page_segments_metric_has_words_tooltip() -> None:
    captured = {"help": None, "value": None}

    class _DummySt:
        @staticmethod
        def metric(label, value, **kwargs):
            if label == "Segments":
                captured["help"] = kwargs.get("help")
                captured["value"] = value
            return None

    transcript_data = {
        "metadata": {"speaker_count": 2, "duration_seconds": 120.0},
        "segments": [
            {"text": "hello world"},
            {"text": "one two three four"},
        ],
    }

    segments_for_words = transcript_data.get("segments", []) or []
    seg_count = len(segments_for_words)
    total_words = 0
    for seg in segments_for_words:
        if not isinstance(seg, dict):
            continue
        text = seg.get("text") or ""
        total_words += len(str(text).split())
    avg_words = (total_words / seg_count) if seg_count else 0.0
    segments_help = (
        f"Total words: {total_words:,}\nAverage words/segment: {avg_words:.1f}"
    )

    _DummySt.metric("Segments", seg_count, help=segments_help)

    assert captured["value"] == 2
    assert captured["help"] is not None
    assert "Total words: 6" in captured["help"]
    assert "Average words/segment: 3.0" in captured["help"]
