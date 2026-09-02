"""Tests for llm_custom_qa readers (no web imports)."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.llm_custom_qa.readers import load_group_member_failures


def test_load_group_member_failures_reads_json_list(tmp_path: Path) -> None:
    root = tmp_path / "run"
    folder = root / "llm_custom_qa"
    folder.mkdir(parents=True)
    (folder / "qa_member_failures.json").write_text(
        json.dumps([{"member": "a"}, "skip", {"member": "b"}]),
        encoding="utf-8",
    )
    rows = load_group_member_failures(root)
    assert rows == [{"member": "a"}, {"member": "b"}]


def test_load_group_member_failures_missing_is_empty(tmp_path: Path) -> None:
    assert load_group_member_failures(tmp_path / "run") == []
