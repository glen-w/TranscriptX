from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.contracts.normalization import (
    assert_module_has_artifact_family,
    assert_no_artifact_family_for_module,
    assert_rel_paths_match_pattern,
    normalize_golden_manifest,
)
from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.core.pipeline.group_analysis_runner import finalize_group_analysis
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.run_schema import (
    RunResultsSummary,
    validate_manifest_shape,
)
from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
    TranscriptRef,
)
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils import transcript_output as transcript_output_module
from transcriptx.core.utils.config import TranscriptXConfig

pytestmark = pytest.mark.integration_core


@pytest.fixture
def _patch_output_paths(tmp_path, monkeypatch):
    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))
    return outputs_root


def test_golden_single_run_manifest_and_run_results_contract(
    _patch_output_paths,
) -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    )
    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats", "transcript_output"],
        persist=False,
    )

    assert result["errors"] == []
    output_dir = Path(result["output_dir"])
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest_shape(manifest)
    normalized = normalize_golden_manifest(manifest)

    assert_module_has_artifact_family(normalized, "stats_data")
    assert_module_has_artifact_family(normalized, "transcript_output")
    assert_no_artifact_family_for_module(normalized, "sentiment", "sentiment_chart")
    assert_rel_paths_match_pattern(normalized, r"^transcripts/.*\.(txt|csv)$")

    run_results_data = json.loads((output_dir / "run_results.json").read_text("utf-8"))
    summary = RunResultsSummary.validate_run_results(run_results_data)
    outcome_by_module = {
        row["module_id"]: row["execution_status"] for row in summary.module_outcomes
    }
    assert outcome_by_module.get("stats") == "run"
    assert outcome_by_module.get("transcript_output") == "run"
    assert "sentiment" not in set(summary.modules_run)
    assert all(
        not (
            row["module_id"] in summary.modules_failed
            and row["execution_status"] == "run"
        )
        for row in summary.module_outcomes
    )


def test_golden_group_run_contract_and_negative_assertion(
    tmp_path: Path, _patch_output_paths
) -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    t1 = tmp_path / "one.json"
    t2 = tmp_path / "two.json"
    shutil.copy(fixture, t1)
    shutil.copy(fixture, t2)

    r1 = run_analysis_pipeline(
        target=TranscriptRef(path=str(t1)),
        selected_modules=["stats"],
        persist=False,
    )
    r2 = run_analysis_pipeline(
        target=TranscriptRef(path=str(t2)),
        selected_modules=["stats"],
        persist=False,
    )
    assert r1["errors"] == []
    assert r2["errors"] == []

    groups_root = tmp_path / "groups"
    groups_root.mkdir(parents=True, exist_ok=True)
    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(groups_root)

    scope = AnalysisScope(
        scope_type="group",
        uuid="golden-group-uuid",
        key="golden-group-key",
        display_name="Golden Group",
    )
    members = [
        FileTranscriptMember(file_path=str(t1), file_name=t1.name, id=1, uuid="m-1"),
        FileTranscriptMember(file_path=str(t2), file_name=t2.name, id=2, uuid="m-2"),
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key=r1["transcript_key"],
            run_id=r1["run_id"],
            order_index=0,
            output_dir=r1["output_dir"],
            module_results=r1.get("module_results", {}),
            modules_run=r1.get("modules_run", []),
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key=r2["transcript_key"],
            run_id=r2["run_id"],
            order_index=1,
            output_dir=r2["output_dir"],
            module_results=r2.get("module_results", {}),
            modules_run=r2.get("modules_run", []),
        ),
    ]

    group_result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[str(t1), str(t2)],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=["stats"],
        config=cfg,
    )
    assert group_result["status"] == "completed"
    group_dir = Path(group_result["group_output_dir"])
    session_rows = group_dir / "stats" / "session_rows.json"
    assert session_rows.exists()
    rows = json.loads(session_rows.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert [row["order_index"] for row in rows] == [0, 1]

    # Negative golden: disabled sentiment should not leak any group sentiment artifacts.
    leaked = list(group_dir.rglob("*sentiment*"))
    assert not leaked
