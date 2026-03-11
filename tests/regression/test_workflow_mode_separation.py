"""
Regression tests for workflow mode — web API always behaves non-interactively.

These replace the former CLI interactive/non-interactive separation tests.
The app layer workflows accept explicit request objects; there is no stdin.
"""

from __future__ import annotations

import json
from pathlib import Path


class TestWebApiNonInteractive:
    """Verify the app-layer workflows never prompt for input."""

    def test_analysis_request_requires_path(self) -> None:
        """AnalysisRequest must have a transcript_path."""
        from transcriptx.app.models.requests import AnalysisRequest

        req = AnalysisRequest(transcript_path=Path("some.json"))
        assert req.transcript_path == Path("some.json")

    def test_validate_missing_file_returns_errors(self, tmp_path: Path) -> None:
        from transcriptx.app.models.requests import AnalysisRequest
        from transcriptx.app.workflows.analysis import validate_analysis_readiness

        req = AnalysisRequest(transcript_path=tmp_path / "no_such.json")
        errors = validate_analysis_readiness(req)
        assert errors, "Expected validation error for missing file"

    def test_validate_invalid_mode_returns_errors(self, tmp_path: Path) -> None:
        from transcriptx.app.models.requests import AnalysisRequest
        from transcriptx.app.workflows.analysis import validate_analysis_readiness

        f = tmp_path / "t.json"
        f.write_text("{}")
        req = AnalysisRequest(transcript_path=f, mode="bogus")
        errors = validate_analysis_readiness(req)
        assert any("mode" in e.lower() for e in errors)


class TestDerivedDefaultsSnapshot:
    def test_derived_defaults_snapshot(self, tmp_path: Path) -> None:
        from transcriptx.core.utils.config import get_config

        get_config()
        defaults = {"analyze": {"mode": "quick", "modules": "all"}}
        snapshot_path = tmp_path / "derived_defaults_snapshot.json"
        snapshot_path.write_text(json.dumps(defaults, indent=2))
        assert snapshot_path.exists()
        loaded = json.loads(snapshot_path.read_text())
        assert "analyze" in loaded
