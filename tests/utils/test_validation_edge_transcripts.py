"""
Validation tests using edge-case transcript fixtures.
"""

import pytest

from transcriptx.core.utils.validation import validate_transcript_file


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture_name",
    [
        "edge_transcript_empty",
        "edge_transcript_ultrashort",
        "edge_transcript_overlapping",
        "edge_transcript_unknown_speaker",
        "edge_transcript_weird_punctuation",
        "edge_transcript_large",
    ],
)
def test_validate_transcript_edge_cases_pass(
    fixture_name, request, edge_transcript_file_factory
):
    """Edge cases with valid structure should validate."""
    data = request.getfixturevalue(fixture_name)
    transcript_path = edge_transcript_file_factory(data, name=f"{fixture_name}.json")
    assert validate_transcript_file(str(transcript_path)) is True


@pytest.mark.unit
def test_validate_transcript_edge_cases_fail(
    edge_transcript_weird_timestamps, edge_transcript_file_factory
):
    """Invalid timestamp ordering should raise validation error."""
    transcript_path = edge_transcript_file_factory(
        edge_transcript_weird_timestamps, name="bad_timestamps.json"
    )
    with pytest.raises(ValueError):
        validate_transcript_file(str(transcript_path))
