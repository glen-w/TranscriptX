"""
Stress/integration: finalize_group_analysis for newly group-functional modules.

Covers insight_eligibility, transcript_output, simplified_transcript, voice_contours,
and lexical_diversity (rows + generic session-bar charts).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.core.pipeline.group_analysis_runner import finalize_group_analysis
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
)
from transcriptx.core.utils.config import TranscriptXConfig

pytestmark = [pytest.mark.integration_core, pytest.mark.unit]


def _patch_output_dirs(monkeypatch: pytest.MonkeyPatch, outputs_root: Path) -> Path:
    """Point OUTPUTS_DIR / GROUP_OUTPUTS_DIR at tmp so charts stay in-tree."""
    import transcriptx.core.utils.output_standards as output_standards_module
    import transcriptx.core.utils.paths as paths_module

    group_root = outputs_root / "groups"
    outputs_root.mkdir(parents=True, exist_ok=True)
    group_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(group_root))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(output_standards_module, "GROUP_OUTPUTS_DIR", str(group_root))
    return group_root


def _member_payloads(order: int) -> dict:
    return {
        "tics": {
            "payload": {
                "global_stats": {"total_tics": order + 1},
                "speaker_stats": {"Alice": {"total_tics": order + 1}},
            }
        },
        "insight_eligibility": {
            "payload": {
                "filtered_segments": [
                    {"segment_index": i, "content_density": 0.5 + 0.1 * i}
                    for i in range(order + 2)
                ],
                "tic_mask": list(range(order + 1)),
                "content_phrases": [f"phrase-{order}-{i}" for i in range(3)],
                "content_densities": {str(i): 0.5 + 0.5 * i for i in range(order + 2)},
            }
        },
        "transcript_output": {
            "payload": {"total_segments": 10 + order, "segments": []},
            "artifacts": [
                {"relative_path": f"transcripts/member{order}.txt"},
                {"relative_path": f"transcripts/member{order}.csv"},
            ],
        },
        "simplified_transcript": {
            "payload": {
                "total_original": 20 + order,
                "total_simplified": 15 + order,
                "simplified": [],
            }
        },
        "voice_contours": {
            "payload": {
                "status": "ok",
                "selected_segment_ids": [f"s{order}-a", f"s{order}-b"],
                "f0_slopes": [
                    {"speaker": "Alice", "slope": 1.0 + order},
                    {"speaker": "Bob", "slope": 2.0 + order},
                ],
            }
        },
        "lexical_diversity": {
            "payload": {
                "global_stats": {
                    "ttr": 0.4 + 0.05 * order,
                    "mtld": 40.0 + order,
                    "hapax_rate": 0.2 + 0.01 * order,
                    "token_count": 100 + 10 * order,
                },
                "speaker_stats": {
                    "Alice": {
                        "ttr": 0.45,
                        "mtld": 42.0,
                        "hapax_rate": 0.22,
                        "token_count": 60 + order,
                    }
                },
            }
        },
    }


def _run_finalize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict, Path]:
    pytest.importorskip("matplotlib")
    group_root = _patch_output_dirs(monkeypatch, tmp_path / "outputs")

    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    t1 = tmp_path / "one.json"
    t2 = tmp_path / "two.json"
    shutil.copy(fixture, t1)
    shutil.copy(fixture, t2)

    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(group_root)

    scope = AnalysisScope(
        scope_type="group",
        uuid="group-functional-stress",
        key="group-functional-key",
        display_name="Group Functional Stress",
    )
    p1, p2 = str(t1), str(t2)
    members = [
        FileTranscriptMember(
            file_path=p1, file_name=t1.name, id=301, uuid="member-uuid-gf-a"
        ),
        FileTranscriptMember(
            file_path=p2, file_name=t2.name, id=302, uuid="member-uuid-gf-b"
        ),
    ]
    selected_with_deps = [
        "insight_eligibility",
        "transcript_output",
        "simplified_transcript",
        "voice_contours",
        "lexical_diversity",
        "tics",
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=p1,
            transcript_key="one",
            run_id="run-a",
            order_index=0,
            output_dir="out/a",
            module_results=_member_payloads(0),
        ),
        PerTranscriptResult(
            transcript_path=p2,
            transcript_key="two",
            run_id="run-b",
            order_index=1,
            output_dir="out/b",
            module_results=_member_payloads(1),
        ),
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[p1, p2],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=selected_with_deps,
        config=cfg,
    )
    return result, Path(result["group_output_dir"])


@pytest.mark.integration_core
def test_finalize_group_functional_modules_rows_blobs_and_charts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, run_dir = _run_finalize(tmp_path, monkeypatch)

    assert result["status"] == "completed"
    aggs = result["aggregations"]
    assert aggs["insight_eligibility"]["output_type"] == "rows"
    assert aggs["transcript_output"]["output_type"] == "blob"
    assert aggs["simplified_transcript"]["output_type"] == "rows"
    assert aggs["voice_contours"]["output_type"] == "rows"
    assert aggs["lexical_diversity"]["output_type"] == "rows"

    ie_sessions = json.loads(
        (run_dir / "insight_eligibility" / "session_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(ie_sessions) == 2
    assert ie_sessions[0]["filtered_segment_count"] == 2
    assert ie_sessions[1]["filtered_segment_count"] == 3
    assert ie_sessions[0]["phrase_count"] == 3

    blob = json.loads(
        (run_dir / "transcript_output" / "transcript_output.json").read_text(
            encoding="utf-8"
        )
    )
    assert blob["aggregation_key"] == "transcript_output"
    assert len(blob["members"]) == 2
    assert blob["members"][0]["total_segments"] == 10
    assert "transcripts/member0.txt" in blob["members"][0]["artifact_relpaths"]

    simp = json.loads(
        (run_dir / "simplified_transcript" / "session_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert [row["removed_count"] for row in simp] == [5, 5]
    assert [row["total_original"] for row in simp] == [20, 21]

    voice = json.loads(
        (run_dir / "voice_contours" / "session_rows.json").read_text(encoding="utf-8")
    )
    assert voice[0]["status"] == "ok"
    assert voice[0]["selected_segment_count"] == 2
    assert voice[0]["f0_slope_count"] == 2
    assert voice[0]["f0_slope_mean"] == 1.5

    lex = json.loads(
        (run_dir / "lexical_diversity" / "session_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(lex) == 2
    assert lex[0]["token_count"] == 100
    assert lex[1]["token_count"] == 110

    # Charted aggs must emit charts under the group run (not redirected to OUTPUTS_DIR).
    for charted in ("lexical_diversity", "simplified_transcript"):
        pngs = list((run_dir / charted).rglob("*.png"))
        assert pngs, f"expected chart PNGs under group run for {charted}"

    # Data-only / blob modules must not invent group chart registry outputs.
    for no_chart in ("insight_eligibility", "voice_contours", "transcript_output"):
        assert not list((run_dir / no_chart).rglob("*.png")), no_chart

    warnings = json.loads(
        (run_dir / "aggregation_warnings.json").read_text(encoding="utf-8")
    )
    schema_failures = [
        w
        for w in warnings
        if isinstance(w, dict) and w.get("code") == "SCHEMA_VALIDATION_FAILED"
    ]
    assert not schema_failures, schema_failures

    chart_failures = [
        w
        for w in warnings
        if isinstance(w, dict) and w.get("code") == "GROUP_CHART_FAILED"
    ]
    assert not chart_failures, chart_failures


@pytest.mark.integration_core
@pytest.mark.parametrize("iteration", range(8))
def test_finalize_group_functional_modules_repeat_stability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, iteration: int
) -> None:
    """Repeat finalize to catch non-deterministic schema/chart flake."""
    del iteration
    result, run_dir = _run_finalize(tmp_path, monkeypatch)
    assert result["status"] == "completed"
    assert list((run_dir / "lexical_diversity").rglob("*.png"))
    assert list((run_dir / "simplified_transcript").rglob("*.png"))
    warnings = json.loads(
        (run_dir / "aggregation_warnings.json").read_text(encoding="utf-8")
    )
    bad = [
        w
        for w in warnings
        if isinstance(w, dict)
        and w.get("code") in {"SCHEMA_VALIDATION_FAILED", "GROUP_CHART_FAILED"}
    ]
    assert not bad, bad


@pytest.mark.integration_core
def test_finalize_group_functional_modules_many_members_scaling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scale member count to stress row writers + generic chart emission."""
    pytest.importorskip("matplotlib")
    group_root = _patch_output_dirs(monkeypatch, tmp_path / "outputs")
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    member_count = 12
    paths: list[str] = []
    members: list[FileTranscriptMember] = []
    per_results: list[PerTranscriptResult] = []
    for i in range(member_count):
        path = tmp_path / f"m{i}.json"
        shutil.copy(fixture, path)
        paths.append(str(path))
        members.append(
            FileTranscriptMember(
                file_path=str(path),
                file_name=path.name,
                id=400 + i,
                uuid=f"member-uuid-{i}",
            )
        )
        per_results.append(
            PerTranscriptResult(
                transcript_path=str(path),
                transcript_key=f"m{i}",
                run_id=f"run-{i}",
                order_index=i,
                output_dir=f"out/{i}",
                module_results=_member_payloads(i % 3),
            )
        )

    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(group_root)
    scope = AnalysisScope(
        scope_type="group",
        uuid="group-functional-scale",
        key="group-functional-scale-key",
        display_name="Group Functional Scale",
    )
    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=paths,
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=[
            "lexical_diversity",
            "simplified_transcript",
            "insight_eligibility",
            "transcript_output",
            "voice_contours",
            "tics",
        ],
        config=cfg,
    )
    assert result["status"] == "completed"
    run_dir = Path(result["group_output_dir"])
    lex = json.loads(
        (run_dir / "lexical_diversity" / "session_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(lex) == member_count
    assert list((run_dir / "lexical_diversity").rglob("*.png"))
    blob = json.loads(
        (run_dir / "transcript_output" / "transcript_output.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(blob["members"]) == member_count
