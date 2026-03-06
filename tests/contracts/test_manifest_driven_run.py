"""
Contract tests: RunManifestInput as canonical pipeline entry.

- Manifest-driven run produces expected output layout and manifest schema.
- CLI-flag run and equivalent manifest run produce the same output structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline


FIXTURE_TRANSCRIPT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "vtt" / "golden" / "simple.json"
)


def _ensure_fixture() -> Path:
    if not FIXTURE_TRANSCRIPT.exists():
        pytest.skip(f"Fixture not found: {FIXTURE_TRANSCRIPT}")
    return FIXTURE_TRANSCRIPT


@pytest.fixture
def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Use an isolated SQLite DB so tests do not use the shared project DB."""
    db_path = tmp_path / "contract_test.db"
    monkeypatch.setenv("TRANSCRIPTX_DATABASE_URL", f"sqlite:///{db_path}")
    import transcriptx.database.database as db_module

    monkeypatch.setattr(db_module, "_db_manager", None)
    yield


def test_manifest_driven_run_produces_output_and_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolated_db
) -> None:
    """Run pipeline with RunManifestInput; assert output dir and artifact manifest exist with manifest_type."""
    fixture = _ensure_fixture()
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(fixture),
        modules=["stats"],
        mode="quick",
        skip_confirm=True,
        skip_speaker_gate=True,
    )
    result = run_analysis_pipeline(manifest=manifest)

    assert not result.get("errors"), result.get("errors")
    output_dir = result.get("output_dir")
    assert output_dir is not None
    run_dir = Path(output_dir)
    assert run_dir.exists()

    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data.get("manifest_type") == "artifact_manifest"
    assert "run_id" in data
    assert "run_metadata" in data
    assert "artifacts" in data

    run_manifest_path = run_dir / ".transcriptx" / "manifest.json"
    if run_manifest_path.exists():
        run_data = json.loads(run_manifest_path.read_text())
        assert run_data.get("manifest_type") == "run_manifest"


def test_cli_equivalent_and_manifest_run_same_structure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolated_db
) -> None:
    """Run once from CLI-style kwargs and once from manifest file; assert same output schema (not byte-identical run_id)."""
    fixture = _ensure_fixture()
    out_base = tmp_path / "outputs"
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(out_base))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))

    manifest_from_kwargs = RunManifestInput.from_cli_kwargs(
        transcript_file=fixture,
        mode="quick",
        modules=["stats"],
        skip_confirm=True,
        skip_speaker_gate=True,
    )
    result1 = run_analysis_pipeline(manifest=manifest_from_kwargs)
    assert not result1.get("errors"), result1.get("errors")
    run_dir1 = Path(result1["output_dir"])

    manifest_file = tmp_path / "run_manifest.json"
    manifest_file.write_text(manifest_from_kwargs.model_dump_json())
    manifest_from_file = RunManifestInput.from_file(manifest_file)
    result2 = run_analysis_pipeline(manifest=manifest_from_file)
    assert not result2.get("errors"), result2.get("errors")
    run_dir2 = Path(result2["output_dir"])

    # Same layout: both have manifest.json with required keys and manifest_type
    for run_dir in (run_dir1, run_dir2):
        assert (run_dir / "manifest.json").exists()
        m = json.loads((run_dir / "manifest.json").read_text())
        assert m.get("manifest_type") == "artifact_manifest"
        assert "run_id" in m and "run_metadata" in m and "artifacts" in m

    # Structure: slug/run_id pattern
    assert run_dir1.parent.name  # slug
    assert run_dir1.name  # run_id
    assert run_dir2.parent.name
    assert run_dir2.name
    # run_ids differ (timestamps)
    assert result1.get("run_id") != result2.get("run_id")
