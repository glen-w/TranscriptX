"""Group-synthesis parity smoke for shared LLM generational store primitives."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.group_llm_synthesis.generation import (
    ensure_generation_dir,
    new_generation_id,
    write_active,
    write_commit,
)
from transcriptx.core.analysis.group_llm_synthesis.digests import InputDigests
from transcriptx.core.analysis.group_llm_synthesis.paths import active_path, commit_path
from transcriptx.core.analysis.llm_generational_store import (
    begin_generation,
    commit_and_activate,
    read_active,
)


def test_group_synthesis_write_active_commit_still_works(tmp_path: Path) -> None:
    """Behavioural parity: existing group APIs remain usable after shared store extract."""
    run_root = tmp_path / "group_run"
    run_root.mkdir()
    gid = new_generation_id()
    ensure_generation_dir(run_root, gid)
    digests = InputDigests(
        global_collect_sha256="a" * 64,
        speaker_rows_sha256="b" * 64,
        combined_input_digest="c" * 64,
    )
    write_commit(
        run_root,
        generation_id=gid,
        digests=digests,
        overall_status="success",
        inventory=[
            {
                "rel_path": "x.json",
                "module": "m",
                "kind": "json",
                "sha256": "d" * 64,
            }
        ],
    )
    write_active(
        run_root,
        generation_id=gid,
        digests=digests,
        overall_status="success",
    )
    assert active_path(run_root).is_file()
    assert commit_path(run_root, gid).is_file()


def test_shared_store_is_usable_alongside_group_api(tmp_path: Path) -> None:
    staged = begin_generation(tmp_path, store_dirname=".topic_shift_enrichment")
    staged.write_json("topic_shift.enrichment.json", {"outcome": "skipped"})
    commit_and_activate(
        staged, rel_paths=["topic_shift.enrichment.json"], status="skipped"
    )
    active = read_active(tmp_path / ".topic_shift_enrichment")
    assert active is not None
    assert active["status"] == "skipped"
