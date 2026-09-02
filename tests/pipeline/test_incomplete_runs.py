"""Incomplete run directory inventory."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from transcriptx.core.pipeline.incomplete_runs import list_incomplete_run_dirs
from transcriptx.core.utils.analysis_locks import transcript_analysis_lock


def test_list_incomplete_run_dirs_empty(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    assert list_incomplete_run_dirs(outputs_dir=outputs, group_outputs_dir=outputs / "groups") == ()


def test_list_incomplete_run_dirs_skips_complete_and_lists_missing(
    tmp_path: Path,
) -> None:
    outputs = tmp_path / "outputs"
    groups = outputs / "groups"
    complete = outputs / "slug-a" / "run-1"
    complete.mkdir(parents=True)
    (complete / "run_results.json").write_text("{}", encoding="utf-8")
    incomplete = outputs / "slug-a" / "run-2"
    incomplete.mkdir(parents=True)
    (incomplete / "manifest.json").write_text("{}", encoding="utf-8")
    group_incomplete = groups / "g1" / "run-g"
    group_incomplete.mkdir(parents=True)
    rows = list_incomplete_run_dirs(outputs_dir=outputs, group_outputs_dir=groups)
    assert {(r.kind, r.slug, r.run_id) for r in rows} == {
        ("transcript", "slug-a", "run-2"),
        ("group", "g1", "run-g"),
    }
    assert all(r.state == "missing" for r in rows)


def test_list_incomplete_run_dirs_skips_hidden(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    hidden = outputs / ".cache" / "x"
    hidden.mkdir(parents=True)
    rows = list_incomplete_run_dirs(
        outputs_dir=outputs, group_outputs_dir=outputs / "groups"
    )
    assert rows == ()


def test_running_without_lock_is_interrupted(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    run_dir = outputs / "slug-a" / "run-live"
    run_dir.mkdir(parents=True)
    (run_dir / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-live",
                "transcript_key": "k",
                "run_status": "running",
                "modules_enabled": ["stats"],
                "modules_run": [],
                "modules_failed": [],
                "modules_skipped": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    rows = list_incomplete_run_dirs(
        outputs_dir=outputs, group_outputs_dir=outputs / "groups"
    )
    assert len(rows) == 1
    assert rows[0].state == "interrupted"


def test_running_with_held_lock_is_in_progress(tmp_path: Path) -> None:
    from transcriptx.core.utils.analysis_locks import canonical_transcript_lock_identity

    outputs = tmp_path / "outputs"
    state_dir = tmp_path / "state"
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    identity = canonical_transcript_lock_identity(transcript)
    run_dir = outputs / "slug-a" / "run-live"
    run_dir.mkdir(parents=True)
    (run_dir / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-live",
                "transcript_key": "k",
                "run_status": "running",
                "modules_enabled": ["stats"],
                "modules_run": [],
                "modules_failed": [],
                "modules_skipped": [],
                "errors": [],
                "analysis_lock": {
                    "kind": "transcript",
                    "identity": identity,
                },
            }
        ),
        encoding="utf-8",
    )
    held = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with transcript_analysis_lock(transcript, state_dir=state_dir):
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=_holder)
    worker.start()
    assert held.wait(timeout=5)
    try:
        rows = list_incomplete_run_dirs(
            outputs_dir=outputs,
            group_outputs_dir=outputs / "groups",
            state_dir=state_dir,
        )
        assert len(rows) == 1
        assert rows[0].state == "in_progress"
    finally:
        release.set()
        worker.join(timeout=5)
