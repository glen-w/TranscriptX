"""Tests for chart path helpers and saving utilities."""

from pathlib import Path

from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    get_global_static_chart_path,
    get_global_dynamic_chart_path,
    get_speaker_static_chart_path,
    get_speaker_dynamic_chart_path,
)
from transcriptx.core.utils.paths import OUTPUTS_DIR


def test_global_chart_paths_created():
    transcript_dir = Path(OUTPUTS_DIR) / "test_outputs"
    output_structure = create_standard_output_structure(
        str(transcript_dir), "sentiment"
    )

    static_path = get_global_static_chart_path(
        output_structure, None, "test_chart", chart_type="sentiment"
    )
    dynamic_path = get_global_dynamic_chart_path(
        output_structure, None, "test_chart", chart_type="sentiment"
    )

    assert "charts/global/static/sentiment" in str(static_path.parent)
    assert "charts/global/dynamic/sentiment" in str(dynamic_path.parent)
    assert static_path.parent.exists()
    assert dynamic_path.parent.exists()


def test_speaker_chart_paths_created():
    transcript_dir = Path(OUTPUTS_DIR) / "test_outputs_speaker"
    output_structure = create_standard_output_structure(
        str(transcript_dir), "sentiment"
    )

    static_path = get_speaker_static_chart_path(
        output_structure, None, "Alice", "rolling_sentiment", chart_type=None
    )
    dynamic_path = get_speaker_dynamic_chart_path(
        output_structure, None, "Alice", "rolling_sentiment", chart_type=None
    )

    assert static_path is not None
    assert dynamic_path is not None
    assert "charts/speakers/Alice/static" in str(static_path.parent)
    assert "charts/speakers/Alice/dynamic" in str(dynamic_path.parent)
    assert static_path.parent.exists()
    assert dynamic_path.parent.exists()
