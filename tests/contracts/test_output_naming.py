"""
Contract tests: output naming invariants. See docs/contracts/output-contract-v1.md §2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline


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

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(FIXTURE),
        modules=["stats"],
        mode="quick",
        skip_confirm=True,
        skip_speaker_gate=True,
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

    # Module dir is directly under run root
    stats_dir = output_dir / "stats"
    assert stats_dir.is_dir(), "module dir should be <run_root>/<module_name>"
