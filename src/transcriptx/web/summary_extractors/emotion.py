"""
Summary extractor for emotion analysis.
"""

from typing import Dict, Any
from . import register_extractor


def extract_emotion_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from emotion analysis data."""
    emotions = data.get("emotions", {})
    if emotions:
        summary["key_metrics"]["Emotions Detected"] = len(emotions)
        # Find dominant emotion
        emotion_counts = {
            emotion: len(segments) for emotion, segments in emotions.items()
        }
        if emotion_counts:
            dominant = max(emotion_counts.items(), key=lambda x: x[1])
            summary["key_metrics"]["Dominant Emotion"] = dominant[0]
            summary["highlights"].append(
                f"Most common emotion: {dominant[0]} ({dominant[1]} segments)"
            )


register_extractor("emotion", extract_emotion_summary)
