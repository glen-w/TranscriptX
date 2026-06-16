from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.utils.html_utils import (
    create_html_report,
    generate_all_modules_section,
    generate_html_content,
    generate_key_moments_section,
    generate_transcript_section,
    wrap_tooltip_text,
)


@pytest.mark.unit
def test_generate_html_content_includes_rich_sections(tmp_path: Path) -> None:
    module_dir = tmp_path / "stats"
    module_dir.mkdir()
    (module_dir / "chart.png").write_text("png", encoding="utf-8")
    (module_dir / "data.csv").write_text("a,b\n", encoding="utf-8")
    (module_dir / "payload.json").write_text("{}", encoding="utf-8")

    html = generate_html_content(
        "meeting",
        {
            "title": "Weekly Meeting",
            "timestamp": "2026-04-26",
            "duration": "10:00",
            "num_speakers": 2,
            "version": "test",
            "errors": ["missing optional chart"],
            "summary_stats": {
                "total_words": 42,
                "segments": 2,
                "avg_segment_length": 21,
                "tic_rate": "0.1",
            },
            "speakers": [
                {"id": "s1", "name": "Alice", "color": "#111111"},
                {"id": "s2", "name": "Bob", "color": "#222222"},
            ],
            "transcript_segments": [
                {
                    "id": "seg-1",
                    "speaker": "s1",
                    "start": "0:01",
                    "text": "Alice met Paris.",
                },
                {
                    "id": "seg-2",
                    "speaker": "s2",
                    "start": "0:05",
                    "text": "Bob replied.",
                },
            ],
            "entities": [{"text": "Paris", "label": "GPE"}],
            "key_moments": [
                {
                    "segment_id": "seg-1",
                    "label": "Decision",
                    "score": "0.9",
                    "summary": "A choice was made.",
                }
            ],
            "module_data": {
                "stats": {"words": 42},
                "highlights": ["one", "two"],
            },
        },
        str(tmp_path),
    )

    assert "Weekly Meeting" in html
    assert "missing optional chart" in html
    assert "Decision" in html
    assert '<mark title="GPE">Paris</mark>' in html
    assert "stats/chart.png" in html
    assert "stats/data.csv" in html
    assert "stats/payload.json" in html
    assert "<li>one</li><li>two</li>" in html


@pytest.mark.unit
def test_create_html_report_writes_report_file(tmp_path: Path) -> None:
    report_path = create_html_report(
        "/tmp/meeting.json",
        str(tmp_path),
        {"title": "Meeting Report", "summary_stats": {"total_words": 3}},
    )

    path = Path(report_path)
    assert path == tmp_path / "meeting_report.html"
    assert path.exists()
    assert "Meeting Report" in path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_section_generators_handle_empty_and_unknown_values(tmp_path: Path) -> None:
    assert generate_key_moments_section([]) == ""
    assert generate_transcript_section([], [], []) == ""
    assert generate_all_modules_section({}, str(tmp_path)) == ""

    tooltip = wrap_tooltip_text(
        "Atlantis", "Speaker 1", "one two three four", wrap_at=2
    )
    assert tooltip == "<b>Atlantis</b><br>Speaker 1<br><i>one two<br>three four</i>"
