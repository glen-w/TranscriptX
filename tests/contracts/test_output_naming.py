"""
Contract tests: output naming invariants. See docs/contracts/output-contract-v1.md §2.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import transcript_output as transcript_output_module
from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.io.speaker_map_resolver import sidecar_path_for

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "vtt" / "golden" / "simple.json"
)


def test_output_dir_naming_slug_run_id_pattern(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run root matches <slug>/<run_id>; module dirs are under run root."""
    if not FIXTURE.exists():
        pytest.skip(f"Fixture not found: {FIXTURE}")
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        paths_module, "GROUP_OUTPUTS_DIR", tmp_path / "outputs" / "groups"
    )
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        output_standards_module, "DIARISED_TRANSCRIPTS_DIR", tmp_path / "transcripts"
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", tmp_path / "transcripts"
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", tmp_path / "outputs")

    transcript_path = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, transcript_path)
    sidecar_path = sidecar_path_for(transcript_path)
    sidecar_path.write_text(
        json.dumps(
            {
                "speaker_map_schema_version": 1,
                "speaker_map": {"SPEAKER_00": "Speaker 1"},
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_provenance": {"source": "test"},
            }
        ),
        encoding="utf-8",
    )

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(transcript_path),
        modules=["stats"],
        mode="quick",
        skip_confirm=True,
    )
    result = run_analysis_pipeline(manifest=manifest)
    assert not result.get("errors"), result.get("errors")

    output_dir = Path(result["output_dir"])
    # output_dir is .../outputs/<slug>/<run_id>
    assert output_dir.exists()
    run_id = output_dir.name
    slug = output_dir.parent.name
    assert slug, "slug non-empty"
    assert run_id, "run_id non-empty"
    # run_id format: YYYYMMDD_HHMMSS_<8hex>
    assert "_" in run_id
    parts = run_id.split("_")
    assert len(parts) >= 3
    assert len(parts[2]) >= 8

    # Stats module writes consolidated report artifacts at the run root.
    assert (output_dir / "report.json").is_file()
    assert (output_dir / "report.md").is_file()
    assert (output_dir / "report.txt").is_file()
