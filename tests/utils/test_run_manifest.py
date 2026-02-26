"""
Tests for run manifest determinism and idempotency.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.run_manifest import create_run_manifest


@pytest.mark.unit
def test_run_manifest_deterministic_hashes(tmp_path):
    """Repeated manifest creation should yield stable hashes."""
    artifact_index = [
        {"path": "sentiment/data/global/test_sentiment.json", "checksum": "sha256:aaa"},
        {"path": "stats/data/global/test_stats.json", "checksum": "sha256:bbb"},
    ]

    config = MagicMock()
    config.to_dict.return_value = {
        "analysis": {"mode": "default"},
        "output": {"version": 1},
    }

    with (
        patch("transcriptx.core.utils.run_manifest.get_config", return_value=config),
        patch(
            "transcriptx.core.utils.module_hashing.compute_module_source_hash",
            return_value="hash",
        ),
    ):

        first = create_run_manifest(
            transcript_hash="sha256:transcript",
            canonical_schema_version="1.0",
            selected_modules=["sentiment", "stats"],
            artifact_index=artifact_index,
            transcript_path="tests/fixtures/vtt/simple.vtt",
        )

        second = create_run_manifest(
            transcript_hash="sha256:transcript",
            canonical_schema_version="1.0",
            selected_modules=["sentiment", "stats"],
            artifact_index=artifact_index,
            transcript_path="tests/fixtures/vtt/simple.vtt",
        )

    assert first.config_hash == second.config_hash
    assert first.transcript_hash == second.transcript_hash
    assert first.artifact_index == second.artifact_index
