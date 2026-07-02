"""Unit tests for Streamlit performance instrumentation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.observability import perf


@pytest.fixture
def perf_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF", "1")
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF_PATH", str(tmp_path / "perf.jsonl"))
    perf._CACHE_MISS_COUNTS.clear()
    if hasattr(perf._RUN_LOCAL, "metrics"):
        delattr(perf._RUN_LOCAL, "metrics")
    if hasattr(perf._RUN_LOCAL, "transcript_paths_seen"):
        delattr(perf._RUN_LOCAL, "transcript_paths_seen")
    yield tmp_path


@pytest.mark.unit
def test_enabled_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF", "0")
    assert perf._enabled() is False
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF", "1")
    assert perf._enabled() is True


@pytest.mark.unit
def test_output_path_prefers_explicit_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "custom.jsonl"
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF_PATH", str(target))
    assert perf._output_path() == target


@pytest.mark.unit
def test_start_and_finish_run_writes_jsonl(perf_env: Path) -> None:
    run_id = perf.start_run(page="home", scenario="smoke")
    assert run_id and run_id != "perf-disabled"
    perf.increment_count("widgets", 2)
    perf.set_cache_state("library", "hit")
    perf.record_file_read(
        perf_env / "t.json",
        section="library",
        purpose="transcript_validation",
    )
    perf.observe_transcript_path(perf_env / "t.json")
    summary = perf.finish_run(notes="done")
    assert summary is not None
    assert summary["counts"]["widgets"] == 2
    assert summary["cache_hit_or_miss"]["library"] == "hit"
    assert summary["counts"]["json_files_read"] == 1
    assert summary["counts"]["transcript_json_files"] == 1
    lines = (perf_env / "perf.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert json.loads(lines[0])["event"] == "run_started"
    assert json.loads(lines[-1])["event"] == "run_summary"


@pytest.mark.unit
def test_section_context_records_timing(perf_env: Path) -> None:
    perf.start_run(page="library")
    with perf.section("load_table", bucket="io"):
        pass
    summary = perf.finish_run()
    assert summary is not None
    assert summary["section_totals_ms"]["io"] >= 0
    assert summary["section_events"][0]["section"] == "load_table"


@pytest.mark.unit
def test_instrument_cached_call_detects_miss(perf_env: Path) -> None:
    perf.start_run(page="home")

    def _body() -> str:
        perf.mark_cache_miss("library_rows")
        return "ok"

    result = perf.instrument_cached_call(
        "library_rows",
        _body,
        bucket="cache",
        counts={"rows": 1},
    )
    assert result == "ok"
    summary = perf.finish_run()
    assert summary is not None
    assert summary["cache_hit_or_miss"]["library_rows"] == "miss"


@pytest.mark.unit
def test_reset_output_clears_file(perf_env: Path) -> None:
    perf.start_run(page="home")
    perf.finish_run()
    out = perf_env / "perf.jsonl"
    assert out.exists()
    perf.reset_output()
    assert not out.exists()


@pytest.mark.unit
def test_warning_handler_increments_warning_count(perf_env: Path) -> None:
    perf._WARNING_HANDLER_INSTALLED = False
    perf.start_run(page="home")
    logger = perf.get_logger()
    logger.warning("instrumented warning")
    summary = perf.finish_run()
    assert summary is not None
    assert summary["warnings_emitted"] >= 1


@pytest.mark.unit
def test_disabled_perf_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_STREAMLIT_PERF", "off")
    assert perf.start_run(page="home") == "perf-disabled"
    perf.increment_count("x")
    assert perf.finish_run() is None
