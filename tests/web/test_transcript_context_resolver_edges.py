"""Additional unit tests for transcript context resolver (0.3.2 navigation era)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services import transcript_context_resolver as tcr


@pytest.mark.unit
def test_paths_match_samefile_and_string_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = tmp_path / "a.json"
    a.write_text("{}", encoding="utf-8")
    b = tmp_path / "b.json"
    b.write_text("{}", encoding="utf-8")
    assert tcr.paths_match(a, a) is True
    assert tcr.paths_match(a, b) is False

    # samefile path when both exist and are hardlinked if possible
    linked = tmp_path / "link.json"
    try:
        linked.hardlink_to(a)
    except OSError:
        linked.write_text("{}", encoding="utf-8")
        # Still equal after resolve when content paths differ but we compare samefile only if both files
        assert tcr.paths_match(str(a), str(a.resolve())) is True
    else:
        assert tcr.paths_match(a, linked) is True

    monkeypatch.setattr(
        Path,
        "expanduser",
        lambda self: (_ for _ in ()).throw(OSError("boom")),
    )
    assert tcr.paths_match("/tmp/x", "/tmp/x") is True
    assert tcr.paths_match("/tmp/x", "/tmp/y") is False


@pytest.mark.unit
def test_latest_run_from_dirs_lexical_when_mtime_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    older = tmp_path / "20260101_aaa"
    newer = tmp_path / "20260102_bbb"
    older.mkdir()
    newer.mkdir()

    real_stat = Path.stat

    def _stat(self, *a, **k):
        raise OSError("no mtime")

    monkeypatch.setattr(Path, "stat", _stat)
    assert tcr._latest_run_from_dirs([older, newer]) == "20260102_bbb"
    assert tcr._latest_run_from_dirs([]) is None
    monkeypatch.setattr(Path, "stat", real_stat)


@pytest.mark.unit
def test_latest_run_from_ids_falls_back_to_max_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.OUTPUTS_DIR",
        tmp_path / "outputs",
    )
    assert (
        tcr._latest_run_from_ids(
            ["20260101_a", "20260103_c", "20260102_b"],
            outputs_slug="slug",
        )
        == "20260103_c"
    )
    assert tcr._latest_run_from_ids([], outputs_slug="slug") is None


@pytest.mark.unit
def test_resolve_uses_index_run_ids_when_no_linked_dirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "meet.json"
    transcript.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "outputs" / "meet"
    run_a = outputs / "20260101_120000_aaaa"
    run_b = outputs / "20260102_120000_bbbb"
    run_a.mkdir(parents=True)
    run_b.mkdir(parents=True)
    import os

    os.utime(run_a, (1_000_000_000, 1_000_000_000))
    os.utime(run_b, (2_000_000_000, 2_000_000_000))

    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {
            "transcripts": {
                "k": {
                    "slug": "meet",
                    "source_path": str(transcript),
                    "runs": ["20260101_120000_aaaa", "20260102_120000_bbbb"],
                }
            }
        },
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.OUTPUTS_DIR",
        tmp_path / "outputs",
    )
    result = tcr.resolve_transcript_context(transcript)
    assert result.subject_id == "meet"
    assert result.run_id == "20260102_120000_bbbb"
