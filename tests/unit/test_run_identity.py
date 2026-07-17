"""Unit tests for run_identity validators and newest-run sort keys.

Critical for cleanup classification and RunIndex ordering (0.4.x).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.utils.run_identity import (
    is_valid_group_uuid,
    is_valid_run_id,
    is_valid_transcript_slug,
    newest_run_sort_key,
    newest_run_sort_key_desc,
    run_summary_newest_key,
)


@pytest.mark.unit
class TestIsValidTranscriptSlug:
    def test_accepts_simple_slug(self) -> None:
        assert is_valid_transcript_slug("interview_01") is True

    def test_rejects_empty_and_reserved(self) -> None:
        assert is_valid_transcript_slug("") is False
        assert is_valid_transcript_slug("groups") is False
        assert is_valid_transcript_slug(".cleanup_staging") is False
        assert is_valid_transcript_slug(".transcriptx_index.json") is False

    def test_rejects_dot_prefix_and_traversal(self) -> None:
        assert is_valid_transcript_slug(".hidden") is False
        assert is_valid_transcript_slug("../escape") is False
        assert is_valid_transcript_slug("a/b") is False
        assert is_valid_transcript_slug("a\\b") is False

    def test_rejects_unsafe_characters(self) -> None:
        assert is_valid_transcript_slug("has space") is False
        assert is_valid_transcript_slug("bad:colon") is False


@pytest.mark.unit
class TestIsValidGroupUuid:
    def test_accepts_uuid_strings(self) -> None:
        assert is_valid_group_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_rejects_empty_invalid_and_dot_prefix(self) -> None:
        assert is_valid_group_uuid("") is False
        assert is_valid_group_uuid("not-a-uuid") is False
        assert is_valid_group_uuid(".550e8400-e29b-41d4-a716-446655440000") is False
        assert is_valid_group_uuid(None) is False  # type: ignore[arg-type]


@pytest.mark.unit
class TestIsValidRunId:
    def test_accepts_production_transcript_and_group_patterns(self) -> None:
        assert is_valid_run_id("20260101_120000_12345678") is True
        assert is_valid_run_id("20260101_120000_abcd1234") is True

    def test_accepts_safe_override_ids(self) -> None:
        assert is_valid_run_id("run_override_1") is True
        assert is_valid_run_id("test.run-id") is True

    def test_rejects_reserved_traversal_and_empty(self) -> None:
        assert is_valid_run_id("") is False
        assert is_valid_run_id("groups") is False
        assert is_valid_run_id(".hidden") is False
        assert is_valid_run_id("a/b") is False
        assert is_valid_run_id("a\\b") is False
        assert is_valid_run_id("has space") is False


@pytest.mark.unit
class TestNewestRunSortKeys:
    def test_missing_mtime_sorts_as_zero(self) -> None:
        assert newest_run_sort_key(mtime_ns=None, run_id="r1") == (0, "r1", "")
        assert newest_run_sort_key_desc(mtime_ns=None, run_id="r1", path="/p") == (
            0,
            "r1",
            "/p",
        )

    def test_desc_orders_higher_mtime_first(self) -> None:
        rows = [
            {"mtime_ns": 1, "run_id": "a", "path": "/a"},
            {"mtime_ns": 3, "run_id": "b", "path": "/b"},
            {"mtime_ns": 2, "run_id": "c", "path": "/c"},
        ]
        ordered = sorted(
            rows,
            key=lambda r: newest_run_sort_key_desc(
                mtime_ns=r["mtime_ns"], run_id=r["run_id"], path=r["path"]
            ),
            reverse=True,
        )
        assert [r["run_id"] for r in ordered] == ["b", "c", "a"]

    def test_run_summary_uses_mtime_ns_when_present(self) -> None:
        run = SimpleNamespace(
            mtime_ns=5_000,
            last_updated=1.0,
            run_id="r",
            run_root=Path("/tmp/r"),
        )
        assert run_summary_newest_key(run) == (5_000, "r", "/tmp/r")

    def test_run_summary_falls_back_to_last_updated_seconds(self) -> None:
        run = SimpleNamespace(
            mtime_ns=None,
            last_updated=2.5,
            run_id="legacy",
            run_root=None,
        )
        assert run_summary_newest_key(run) == (
            int(2.5 * 1_000_000_000),
            "legacy",
            "",
        )

    def test_run_summary_missing_fields_defaults(self) -> None:
        run = SimpleNamespace()
        assert run_summary_newest_key(run) == (0, "", "")
