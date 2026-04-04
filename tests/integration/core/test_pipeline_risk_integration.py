"""
Integration tests for high failure-risk pipeline paths.

Covers: multi-module runs, manifest entrypoint, dependency expansion (summary→highlights),
and fail-fast target validation. Uses tmp output dirs and mini_transcript; no DB/models/docker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import transcript_output as transcript_output_module

pytestmark = pytest.mark.heavy


def _fixture_mini_transcript() -> Path:
    path = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not path.exists():
        pytest.skip("fixtures/mini_transcript.json not found")
    return path


def _patch_output_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    outputs_root.mkdir()
    transcripts_root.mkdir()
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(transcripts_root),
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(transcripts_root),
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))


@pytest.mark.integration_core
def test_pipeline_multi_module_stats_and_transcript_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DAG run with two independent-ish modules: stats artifacts + human transcript files."""
    _patch_output_roots(tmp_path, monkeypatch)
    fixture_path = _fixture_mini_transcript()

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats", "transcript_output"],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    output_dir = Path(result["output_dir"])
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "report.md").is_file() or (output_dir / "report.txt").is_file()
    transcripts_dir = output_dir / "transcripts"
    assert transcripts_dir.is_dir()
    assert list(transcripts_dir.glob("*.txt")) or list(transcripts_dir.glob("*.csv"))


@pytest.mark.integration_core
def test_pipeline_summary_expands_highlights_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requesting only ``summary`` must run ``highlights`` first; both leave artifacts."""
    _patch_output_roots(tmp_path, monkeypatch)
    fixture_path = _fixture_mini_transcript()

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["summary"],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    modules_run = result.get("modules_run") or []
    assert "highlights" in modules_run
    assert "summary" in modules_run
    assert modules_run.index("highlights") < modules_run.index("summary")

    output_dir = Path(result["output_dir"])
    assert list(output_dir.glob("highlights/data/global/*_highlights.json"))
    assert list(output_dir.glob("summary/data/global/*_summary.json"))


@pytest.mark.integration_core
def test_run_analysis_pipeline_via_run_manifest_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manifest-shaped entrypoint (web/API) must match direct run for a minimal module."""
    _patch_output_roots(tmp_path, monkeypatch)
    fixture_path = _fixture_mini_transcript()

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(fixture_path.resolve()),
        modules=["stats"],
        mode="quick",
        profile=None,
        skip_confirm=True,
        persist=False,
        run_id=None,
    )
    result = run_analysis_pipeline(manifest=manifest)

    assert result.get("errors") == [], result.get("errors")
    output_dir = Path(result["output_dir"])
    rr = json.loads((output_dir / "run_results.json").read_text(encoding="utf-8"))
    assert "stats" in (rr.get("modules_run") or [])


@pytest.mark.integration_core
def test_pipeline_raises_file_not_found_for_missing_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_output_roots(tmp_path, monkeypatch)
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        run_analysis_pipeline(
            target=TranscriptRef(path=str(missing)),
            selected_modules=["stats"],
            persist=False,
        )


@pytest.mark.integration_core
def test_pipeline_raises_value_error_for_invalid_json_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_output_roots(tmp_path, monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        run_analysis_pipeline(
            target=TranscriptRef(path=str(bad)),
            selected_modules=["stats"],
            persist=False,
        )


@pytest.mark.integration_core
def test_pipeline_raises_value_error_for_non_json_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_output_roots(tmp_path, monkeypatch)
    wrong = tmp_path / "x.txt"
    wrong.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="transcript JSON"):
        run_analysis_pipeline(
            target=TranscriptRef(path=str(wrong)),
            selected_modules=["stats"],
            persist=False,
        )
