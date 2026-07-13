"""Extended unit tests for group row writer content rows and CSV drop keys."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from transcriptx.core.output.group_row_writer import write_row_outputs


@pytest.mark.unit
def test_write_row_outputs_content_rows_and_bundle(tmp_path: Path) -> None:
    written, warning = write_row_outputs(
        base_dir=tmp_path,
        agg_id="highlights",
        session_rows=[{"transcript_id": "t1", "order_index": 0, "n": 1}],
        speaker_rows=[],
        metrics_spec=[{"name": "n", "format": "int"}],
        content_rows=[
            {
                "id": "h1",
                "text": "quote",
                "score": 0.9,
                "debug": "secret",
            }
        ],
        content_rows_name="highlight_rows",
        bundle=True,
        drop_csv_keys=["debug"],
    )
    assert written is True
    assert warning is None
    agg_dir = tmp_path / "highlights"
    content = json.loads((agg_dir / "highlight_rows.json").read_text(encoding="utf-8"))
    assert content[0]["debug"] == "secret"
    with (agg_dir / "highlight_rows.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert "debug" not in rows[0]
    assert rows[0]["text"] == "quote"
    bundle = json.loads((agg_dir / "aggregation.json").read_text(encoding="utf-8"))
    assert "highlight_rows" in bundle
    assert bundle["highlight_rows"][0]["id"] == "h1"


@pytest.mark.unit
def test_write_row_outputs_without_content_name_skips_content_files(
    tmp_path: Path,
) -> None:
    written, warning = write_row_outputs(
        base_dir=tmp_path,
        agg_id="demo",
        session_rows=[{"transcript_id": "t1", "order_index": 0}],
        speaker_rows=[],
        content_rows=[{"id": "x"}],
        content_rows_name=None,
        bundle=True,
    )
    assert written is True
    assert warning is None
    assert not (tmp_path / "demo" / "content_rows.json").exists()
    bundle = json.loads((tmp_path / "demo" / "aggregation.json").read_text())
    assert "content_rows" not in bundle
