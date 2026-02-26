"""Snapshot-style tests for stats report output layout."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.stats.stats_report import (  # type: ignore[import]
    build_stats_payload,
    render_stats_markdown,
)


class DummyContext:
    def __init__(self, base_name: str, transcript_dir: Path, results: dict) -> None:
        self._base_name = base_name
        self._dir = str(transcript_dir)
        self._results = results

    def get_analysis_result(self, module_id: str) -> object | None:
        return self._results.get(module_id)

    def get_base_name(self) -> str:
        return self._base_name

    def get_transcript_dir(self) -> str:
        return self._dir

    def get_run_id(self) -> str:
        return "run_123"

    def get_transcript_key(self) -> str:
        return "transcript_key_abc"


def _make_segments_with_warning() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Hello world",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Missing time",
        },
    ]


def _make_stats_results() -> dict:
    return {
        "speaker_stats": [
            (120.0, "Alice", 600, 10, 0.02, 60.0),
            (60.0, "Bob", 300, 5, 0.01, 60.0),
        ],
        "sentiment_summary": {
            "Alice": {"compound": 0.1, "pos": 0.2, "neu": 0.7, "neg": 0.1},
            "Bob": {"compound": -0.1, "pos": 0.1, "neu": 0.8, "neg": 0.1},
        },
    }


def test_stats_report_markdown_sections_order(tmp_path: Path) -> None:
    base_name = "sample"
    sentiment_out = tmp_path / "sentiment" / "data" / "global"
    sentiment_out.mkdir(parents=True)
    (sentiment_out / f"{base_name}_sentiment_summary.json").write_text("{}")

    context = DummyContext(
        base_name, tmp_path, results={"sentiment": {"status": "success"}}
    )
    payload = build_stats_payload(
        context,
        _make_segments_with_warning(),
        _make_stats_results(),
        module_data={},
    )

    md = render_stats_markdown(payload)
    sections = [
        "# Overall Stats Report",
        "## Provenance",
        "## Module Status",
        "## Speaker Statistics",
        "## Sentiment",
        "## Derived Insights",
        "## Warnings",
        "## Outputs Index",
    ]
    positions = [md.find(section) for section in sections]
    assert all(pos != -1 for pos in positions)
    assert positions == sorted(positions)
