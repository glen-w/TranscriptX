"""Canonical group truth projection fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.pipeline.run_outcome_truth import project_group_outcomes


def _write(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _member_run(
    base: Path,
    member_id: str,
    *,
    modules_enabled: list[str],
    modules_run: list[str],
    modules_skipped: list[dict] | None = None,
    modules_failed: list[str] | None = None,
    module_outcomes: list[dict] | None = None,
) -> Path:
    out = base / f"member_{member_id}"
    _write(
        out / "run_results.json",
        {
            "schema_version": 1,
            "run_id": f"r_{member_id}",
            "transcript_key": f"tk_{member_id}",
            "modules_enabled": modules_enabled,
            "modules_run": modules_run,
            "modules_skipped": modules_skipped or [],
            "modules_failed": modules_failed or [],
            "errors": [],
            "module_outcomes": module_outcomes or [],
        },
    )
    return out


def _group_run(
    tmp_path: Path,
    *,
    group_modules_enabled: list[str],
    group_modules_run: list[str],
    group_modules_skipped: list[dict] | None = None,
    group_modules_failed: list[str] | None = None,
    members: list[dict] | None = None,
    phase_rows: list[dict] | None = None,
) -> Path:
    run_dir = tmp_path / "group_run"
    _write(
        run_dir / "run_results.json",
        {
            "schema_version": 1,
            "run_id": "group_r1",
            "transcript_key": "group_tk",
            "modules_enabled": group_modules_enabled,
            "modules_run": group_modules_run,
            "modules_skipped": group_modules_skipped or [],
            "modules_failed": group_modules_failed or [],
            "errors": [],
            "module_outcomes": [],
        },
    )
    _write(
        run_dir / "group_member_runs.json",
        {"schema_version": 1, "members": members or []},
    )
    if phase_rows is not None:
        _write(run_dir / "aggregation_warnings.json", phase_rows)
    return run_dir


def test_group_all_members_succeeded(tmp_path: Path) -> None:
    tmp = tmp_path / "group_all_succeeded"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["sentiment"], modules_run=["sentiment"])
    m2 = _member_run(tmp, "2", modules_enabled=["sentiment"], modules_run=["sentiment"])
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["sentiment"],
        group_modules_run=["sentiment"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
        ],
        phase_rows=[],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "succeeded"
    assert outcome.any_member_usable is True
    assert outcome.missing_member_outcomes == 0


def test_group_partial_blocked_and_skipped_members(tmp_path: Path) -> None:
    tmp = tmp_path / "group_partial_blocked"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["emotion"], modules_run=["emotion"])
    m2 = _member_run(
        tmp,
        "2",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[
            {"module": "emotion", "reason": "dep", "execution_status": "blocked"}
        ],
    )
    m3 = _member_run(
        tmp,
        "3",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[
            {"module": "emotion", "reason": "preset", "execution_status": "skipped"}
        ],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["emotion"],
        group_modules_run=["emotion"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
            {
                "order_index": 2,
                "transcript_path": "c.json",
                "transcript_key": "c",
                "run_id": "r3",
                "output_dir": str(m3),
            },
        ],
        phase_rows=[],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "partial"


def test_group_failed_when_no_member_usable(tmp_path: Path) -> None:
    tmp = tmp_path / "group_failed"
    tmp.mkdir(parents=True)
    m1 = _member_run(
        tmp,
        "1",
        modules_enabled=["topic_modeling"],
        modules_run=[],
        modules_failed=["topic_modeling"],
    )
    m2 = _member_run(
        tmp,
        "2",
        modules_enabled=["topic_modeling"],
        modules_run=[],
        modules_failed=["topic_modeling"],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["topic_modeling"],
        group_modules_run=[],
        group_modules_failed=["topic_modeling"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
        ],
        phase_rows=[],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "failed"
    assert outcome.any_member_usable is False


def test_group_cache_hit_remains_succeeded_metadata(tmp_path: Path) -> None:
    tmp = tmp_path / "group_cache"
    tmp.mkdir(parents=True)
    m1 = _member_run(
        tmp,
        "1",
        modules_enabled=["sentiment"],
        modules_run=["sentiment"],
        module_outcomes=[{"module_id": "sentiment", "used_cache": True}],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["sentiment"],
        group_modules_run=["sentiment"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
        ],
        phase_rows=[],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "succeeded"
    assert outcome.members[0].outcomes[0].used_cache is True


def test_group_partial_when_group_phase_warning_exists(tmp_path: Path) -> None:
    tmp = tmp_path / "group_phase_partial"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["stats"], modules_run=["stats"])
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
        ],
        phase_rows=[{"code": "GROUP_CHART_FAILED", "message": "chart fail"}],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "partial"


def test_group_terminal_failure_overrides_to_failed(tmp_path: Path) -> None:
    tmp = tmp_path / "group_terminal"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["stats"], modules_run=["stats"])
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
        ],
        phase_rows=[{"code": "GROUP_FINALIZATION_FAILED", "message": "terminal"}],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "failed"
    assert outcome.group_phase_terminal_failure is True


def test_group_missing_member_run_results_is_unavailable(tmp_path: Path) -> None:
    tmp = tmp_path / "group_missing_member"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["stats"], modules_run=["stats"])
    missing = tmp / "member_missing"
    missing.mkdir(parents=True)
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(missing),
            },
        ],
        phase_rows=[],
    )
    outcome = project_group_outcomes(run_dir)
    assert outcome.missing_member_outcomes == 1
    assert any(m.outcome_unavailable for m in outcome.members)


def test_group_missing_group_rollup_uses_member_truth(tmp_path: Path) -> None:
    tmp = tmp_path / "group_missing_rollup"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["stats"], modules_run=["stats"])
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
        ],
        phase_rows=[],
    )
    (run_dir / "run_results.json").unlink()
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "succeeded"


def test_group_missing_member_list_uses_group_rollup(tmp_path: Path) -> None:
    tmp = tmp_path / "group_missing_members"
    tmp.mkdir(parents=True)
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[],
        phase_rows=[],
    )
    (run_dir / "group_member_runs.json").unlink()
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "succeeded"
    assert outcome.members == []


def test_group_malformed_phase_metadata_does_not_overclaim(tmp_path: Path) -> None:
    tmp = tmp_path / "group_malformed_phase"
    tmp.mkdir(parents=True)
    m1 = _member_run(tmp, "1", modules_enabled=["stats"], modules_run=["stats"])
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["stats"],
        group_modules_run=["stats"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
        ],
        phase_rows=[],
    )
    (run_dir / "aggregation_warnings.json").write_text("{bad", encoding="utf-8")
    outcome = project_group_outcomes(run_dir)
    assert outcome.status == "succeeded"
    assert outcome.group_phase_metadata == []


def test_group_all_members_blocked(tmp_path: Path) -> None:
    tmp = tmp_path / "group_all_blocked"
    tmp.mkdir(parents=True)
    m1 = _member_run(
        tmp,
        "1",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[{"module": "emotion", "execution_status": "blocked"}],
    )
    m2 = _member_run(
        tmp,
        "2",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[{"module": "emotion", "execution_status": "blocked"}],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["emotion"],
        group_modules_run=[],
        group_modules_skipped=[{"module": "emotion", "execution_status": "blocked"}],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
        ],
        phase_rows=[],
    )
    assert project_group_outcomes(run_dir).status == "blocked"


def test_group_all_members_skipped(tmp_path: Path) -> None:
    tmp = tmp_path / "group_all_skipped"
    tmp.mkdir(parents=True)
    m1 = _member_run(
        tmp,
        "1",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[{"module": "emotion", "execution_status": "skipped"}],
    )
    m2 = _member_run(
        tmp,
        "2",
        modules_enabled=["emotion"],
        modules_run=[],
        modules_skipped=[{"module": "emotion", "execution_status": "skipped"}],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["emotion"],
        group_modules_run=[],
        group_modules_skipped=[{"module": "emotion", "execution_status": "skipped"}],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
        ],
        phase_rows=[],
    )
    assert project_group_outcomes(run_dir).status == "skipped"


def test_group_no_success_mixed_failed_blocked_skipped_is_failed(
    tmp_path: Path,
) -> None:
    tmp = tmp_path / "group_mixed_nosuccess"
    tmp.mkdir(parents=True)
    m1 = _member_run(
        tmp, "1", modules_enabled=["m"], modules_run=[], modules_failed=["m"]
    )
    m2 = _member_run(
        tmp,
        "2",
        modules_enabled=["m"],
        modules_run=[],
        modules_skipped=[{"module": "m", "execution_status": "blocked"}],
    )
    m3 = _member_run(
        tmp,
        "3",
        modules_enabled=["m"],
        modules_run=[],
        modules_skipped=[{"module": "m", "execution_status": "skipped"}],
    )
    run_dir = _group_run(
        tmp,
        group_modules_enabled=["m"],
        group_modules_run=[],
        group_modules_failed=["m"],
        members=[
            {
                "order_index": 0,
                "transcript_path": "a.json",
                "transcript_key": "a",
                "run_id": "r1",
                "output_dir": str(m1),
            },
            {
                "order_index": 1,
                "transcript_path": "b.json",
                "transcript_key": "b",
                "run_id": "r2",
                "output_dir": str(m2),
            },
            {
                "order_index": 2,
                "transcript_path": "c.json",
                "transcript_key": "c",
                "run_id": "r3",
                "output_dir": str(m3),
            },
        ],
        phase_rows=[],
    )
    assert project_group_outcomes(run_dir).status == "failed"
