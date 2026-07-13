"""Unit tests for summary charts PDF builder."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from transcriptx.core.analysis.summary import charts_pdf


def _write_png(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(40, 120, 200)).save(path)


@pytest.mark.unit
def test_build_charts_pdf_with_sentiment_and_summary_pngs(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_png(run / "sentiment" / "charts" / "global" / "x.png")
    _write_png(run / "summary" / "charts" / "global" / "x.png")

    out_pdf = tmp_path / "all_charts.pdf"
    result = charts_pdf.build_charts_pdf(run, out_pdf)

    assert result is not None
    assert result == out_pdf
    assert result.exists()
    assert result.stat().st_size > 0


@pytest.mark.unit
def test_build_charts_pdf_empty_run_returns_none(tmp_path: Path) -> None:
    run = tmp_path / "empty_run"
    run.mkdir()
    assert charts_pdf.build_charts_pdf(run, tmp_path / "out.pdf") is None


@pytest.mark.unit
def test_image_flowable_missing_file_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "nope.png"
    calls: list[tuple] = []

    class FakeRLImage:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

    assert charts_pdf._image_flowable(missing, 400.0, FakeRLImage) is None
    assert calls == []
