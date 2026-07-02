"""Unit tests for voice contour helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from transcriptx.core.analysis.voice import contours as vc


@pytest.mark.unit
def test_f0_slope_returns_none_for_short_series() -> None:
    assert vc._f0_slope_st_per_s([0.0], [120.0]) is None
    assert vc._f0_slope_st_per_s([], []) is None


@pytest.mark.unit
def test_f0_slope_computes_for_valid_series() -> None:
    times = [0.0, 0.1, 0.2, 0.3]
    f0 = [100.0, 110.0, 120.0, 130.0]
    slope = vc._f0_slope_st_per_s(times, f0)
    assert slope is not None
    assert slope > 0


@pytest.mark.unit
def test_compute_f0_contour_without_librosa_returns_empty() -> None:
    wave = np.zeros(1000, dtype=np.float64)
    with patch.dict("sys.modules", {"librosa": None}):
        times, f0 = vc._compute_f0_contour(wave, sample_rate=16000)
    assert times == []
    assert f0 == []


@pytest.mark.unit
def test_compute_f0_contour_uses_librosa_when_available() -> None:
    wave = np.ones(4096, dtype=np.float64)
    fake_librosa = MagicMock()
    fake_librosa.yin.return_value = np.array([100.0, 110.0, 0.0, 120.0])
    with patch.dict("sys.modules", {"librosa": fake_librosa}):
        times, f0 = vc._compute_f0_contour(wave, sample_rate=16000)
    assert len(times) == len(f0)
    assert f0
