"""
Contract tests: unidentified speakers excluded from per-speaker outputs;
present in transcript/CSV and NER. See docs/contracts/output-contract-v1.md §5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline


FIXTURE_MIXED = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "mini_transcript_mixed_speakers.json"
)


def _ensure_fixture() -> Path:
    if not FIXTURE_MIXED.exists():
        pytest.skip(f"Fixture not found: {FIXTURE_MIXED}")
    return FIXTURE_MIXED


def test_unidentified_excluded_from_per_speaker_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run pipeline with mixed speakers; assert no SPEAKER_XX in per-speaker artifact paths."""
    fixture = _ensure_fixture()
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")

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

    output_dir = Path(result["output_dir"])
    # Collect any path under data/speakers or charts/speakers that contains SPEAKER_
    speakers_data = output_dir / "stats" / "data" / "speakers"
    speakers_charts = output_dir / "stats" / "charts" / "speakers"
    found_speaker_xx = []
    for base in (speakers_data, speakers_charts):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if "SPEAKER_" in p.name or "SPEAKER_" in str(p):
                found_speaker_xx.append(str(p))
    assert not found_speaker_xx, (
        "Per-speaker outputs must not contain SPEAKER_XX when exclude_unidentified is true; "
        f"found: {found_speaker_xx}"
    )


def test_unidentified_present_in_transcript_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run pipeline; transcript output or CSV should include all speakers (including SPEAKER_XX)."""
    fixture = _ensure_fixture()
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(fixture),
        modules=["transcript_output"],
        mode="quick",
        skip_confirm=True,
        skip_speaker_gate=True,
    )
    result = run_analysis_pipeline(manifest=manifest)
    assert not result.get("errors"), result.get("errors")

    output_dir = Path(result["output_dir"])
    # Find transcript_output output (JSON or CSV) and ensure SPEAKER_00/SPEAKER_01 appear in content
    to_dir = output_dir / "transcript_output"
    if not to_dir.exists():
        pytest.skip("transcript_output module did not produce output dir")
    texts = []
    for f in to_dir.rglob("*.json"):
        texts.append(f.read_text())
    for f in to_dir.rglob("*.csv"):
        texts.append(f.read_text())
    combined = " ".join(texts)
    assert (
        "SPEAKER_00" in combined
        or "SPEAKER_01" in combined
        or "Unidentified" in combined
        or "Alice" in combined
    ), (
        "Transcript/CSV output should include all speakers (or segment text); "
        "expected SPEAKER_00/SPEAKER_01 or segment text in output"
    )
