from pathlib import Path

from transcriptx.core.output.group_row_writer import write_row_outputs  # type: ignore[import]


def test_write_row_outputs_validation_failure(tmp_path: Path) -> None:
    written, warning = write_row_outputs(
        base_dir=tmp_path,
        agg_id="demo",
        session_rows=[{"order_index": 0}],
        speaker_rows=[{"canonical_speaker_id": 1}],
        metrics_spec=None,
        bundle=True,
    )
    assert not written
    assert warning is not None
    assert warning["code"] == "SCHEMA_VALIDATION_FAILED"


def test_write_row_outputs_success(tmp_path: Path) -> None:
    written, warning = write_row_outputs(
        base_dir=tmp_path,
        agg_id="demo",
        session_rows=[{"transcript_id": "t1", "order_index": 0, "metric": 1.5}],
        speaker_rows=[{"canonical_speaker_id": 1, "display_name": "A", "metric": 2}],
        metrics_spec=[{"name": "metric", "format": "float"}],
        bundle=True,
    )
    assert written
    assert warning is None
    agg_dir = tmp_path / "demo"
    assert (agg_dir / "session_rows.json").exists()
    assert (agg_dir / "speaker_rows.json").exists()
    assert (agg_dir / "session_rows.csv").exists()
    assert (agg_dir / "speaker_rows.csv").exists()
    assert (agg_dir / "metrics_spec.json").exists()
    assert (agg_dir / "aggregation.json").exists()
