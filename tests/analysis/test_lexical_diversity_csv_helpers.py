"""Unit tests for lexical diversity CSV helpers (0.3.4 module)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from transcriptx.core.analysis import lexical_diversity as ld


@pytest.mark.unit
def test_csv_number_formats_and_empty() -> None:
    assert ld._csv_number(None) == ""
    assert ld._csv_number(1.23456789) == "1.234568"
    assert ld._csv_number(0) == "0.000000"


@pytest.mark.unit
def test_save_lexical_diversity_csv_writes_scopes(tmp_path: Path) -> None:
    payload = {
        "global_stats": {
            "token_count": 10,
            "type_count": 5,
            "hapax_count": 2,
            "ttr": 0.5,
            "mtld": 12.0,
            "hapax_rate": 0.2,
        },
        "speaker_stats": {
            "Bob": {
                "token_count": 4,
                "type_count": 3,
                "hapax_count": 1,
                "ttr": 0.75,
                "mtld": None,
                "hapax_rate": 0.25,
            },
            "Alice": {
                "token_count": 6,
                "type_count": 4,
                "hapax_count": 1,
                "ttr": 0.66,
                "mtld": 8.0,
                "hapax_rate": 0.16,
            },
        },
        "time_buckets": [
            {
                "bucket_start": 0.0,
                "bucket_end": 60.0,
                "token_count": 3,
                "type_count": 2,
                "hapax_count": 1,
                "ttr": 0.66,
                "mtld": 4.0,
                "hapax_rate": 0.33,
            }
        ],
    }
    out = tmp_path / "nested" / "ld.csv"
    ld._save_lexical_diversity_csv(payload, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    scopes = [r["scope"] for r in rows]
    assert scopes[0] == "global"
    assert "speaker" in scopes and "time_bucket" in scopes
    speakers = [r["speaker"] for r in rows if r["scope"] == "speaker"]
    assert speakers == ["Alice", "Bob"]
    bucket = next(r for r in rows if r["scope"] == "time_bucket")
    assert bucket["bucket_start"] == "0.000000"
    assert bucket["bucket_end"] == "60.000000"
    bob = next(r for r in rows if r["speaker"] == "Bob")
    assert bob["mtld"] == ""


@pytest.mark.unit
def test_plot_lexical_diversity_charts_skips_empty_and_null_metrics() -> None:
    class _Out:
        def __init__(self) -> None:
            self.charts: list[str] = []

        def save_chart(self, spec, **_kwargs):
            self.charts.append(spec.name)

    empty = _Out()
    ld._plot_lexical_diversity_charts({"speaker_stats": {}}, empty)
    assert empty.charts == []

    out = _Out()
    ld._plot_lexical_diversity_charts(
        {
            "speaker_stats": {
                "A": {"ttr": 0.5, "mtld": None, "hapax_rate": 0.1},
                "B": {"ttr": None, "mtld": 3.0, "hapax_rate": None},
            }
        },
        out,
    )
    assert "lexical-ttr" in out.charts
    assert "lexical-mtld" in out.charts
    assert "lexical-hapax-rate" in out.charts


@pytest.mark.unit
def test_plot_lexical_diversity_charts_excludes_unnamed_speakers() -> None:
    class _Out:
        def __init__(self) -> None:
            self.specs: list = []

        def save_chart(self, spec, **_kwargs):
            self.specs.append(spec)

    out = _Out()
    ld._plot_lexical_diversity_charts(
        {
            "speaker_stats": {
                "Ana": {"ttr": 0.5, "mtld": 10.0, "hapax_rate": 0.53},
                "Glen": {"ttr": 0.48, "mtld": 9.0, "hapax_rate": 0.52},
                "SPEAKER_03": {"ttr": 0.9, "mtld": 2.0, "hapax_rate": 0.8},
            }
        },
        out,
    )
    assert out.specs
    for spec in out.specs:
        assert "SPEAKER_03" not in spec.categories
        assert set(spec.categories) <= {"Ana", "Glen"}
