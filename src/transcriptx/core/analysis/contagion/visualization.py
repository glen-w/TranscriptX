"""
Visualization utilities for contagion analysis.
"""

from __future__ import annotations

from typing import Any, Dict

from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.viz_ids import VIZ_CONTAGION_MATRIX
from transcriptx.core.viz.specs import HeatmapMatrixSpec


def create_contagion_matrix(
    results: Dict[str, Any],
    output_service: Any,
) -> None:
    """Create contagion matrix visualization."""
    speaker_emotions = results.get("speaker_emotions", {})
    contagion_summary = results.get("contagion_summary", {})
    emotion_type = results.get("emotion_type", "unknown")

    seen = set()
    speakers = []
    for s in speaker_emotions.keys():
        if s and s not in seen and is_named_speaker(s):
            speakers.append(s)
            seen.add(s)

    if len(speakers) > 1:
        timeline = results.get("timeline", [])
        emotions = sorted({emo for _, emo in timeline})

        matrix = [
            [
                sum(
                    contagion_summary.get(f"{from_spk}->{to_spk}", {}).get(emo, 0)
                    for emo in emotions
                )
                for to_spk in speakers
            ]
            for from_spk in speakers
        ]

        spec = HeatmapMatrixSpec(
            viz_id=VIZ_CONTAGION_MATRIX,
            module="contagion",
            name="contagion_matrix",
            scope="global",
            chart_intent="heatmap_matrix",
            title=f"Emotional Contagion Matrix ({emotion_type})",
            x_label="To Speaker",
            y_label="From Speaker",
            z=matrix,
            x_labels=speakers,
            y_labels=speakers,
        )
        output_service.save_chart(spec, chart_type="matrix")
