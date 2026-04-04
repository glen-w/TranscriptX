"""
Tests for run report serialization and persistence.
"""

from pathlib import Path

from transcriptx.core.utils.run_report import ModuleResult, RunReport, save_run_report


def test_run_report_record_and_serialize(tmp_path: Path):
    report = RunReport(transcript_hash="sha256:abc", run_id="run123")
    report.record_module("sentiment", ModuleResult.RUN, duration_seconds=1.2)
    report.record_module("stats", ModuleResult.SKIP, reason="Requires segments")
    report.warnings.append("warning")
    report.errors.append("error")

    payload = report.to_dict()
    assert payload["transcript_hash"] == "sha256:abc"
    assert payload["run_id"] == "run123"
    assert payload["modules"]["sentiment"]["status"] == "RUN"
    assert payload["modules"]["stats"]["reason"] == "Requires segments"
    assert payload["warnings"] == ["warning"]
    assert payload["errors"] == ["error"]


def test_save_run_report(tmp_path: Path):
    report = RunReport(transcript_hash="sha256:abc", run_id="run123")
    report.record_module("sentiment", ModuleResult.RUN)

    report_path = save_run_report(report, tmp_path)
    assert report_path.exists()
    assert report_path.name == "run_report.json"
    assert report_path.parent.name == ".transcriptx"
