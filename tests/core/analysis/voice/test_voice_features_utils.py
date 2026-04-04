from __future__ import annotations

import numpy as np
import pytest

from transcriptx.core.analysis.voice import features as vf


def test_compute_rms_db_handles_empty_and_zero_wave() -> None:
    assert vf.compute_rms_db(np.array([], dtype=np.float32)) is None
    assert vf.compute_rms_db(np.zeros(16, dtype=np.float32)) is None


def test_compute_rms_db_returns_expected_value() -> None:
    wave = np.array([0.5, -0.5], dtype=np.float32)
    rms_db = vf.compute_rms_db(wave)
    assert rms_db is not None
    assert pytest.approx(-6.0206, rel=1e-3) == rms_db


def test_compute_voiced_ratio_returns_none_without_webrtcvad(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ImportError("missing")

    monkeypatch.setattr(vf, "optional_import", _raise)
    ratio = vf.compute_voiced_ratio(np.ones(320, dtype=np.float32), 16000, vad_mode=1)
    assert ratio is None


def test_compute_voiced_ratio_with_mock_vad(monkeypatch) -> None:
    class DummyVad:
        def __init__(self, _mode: int) -> None:
            self.calls = 0

        def is_speech(self, _frame, _sr: int) -> bool:
            self.calls += 1
            return self.calls == 1

    class DummyModule:
        Vad = DummyVad

    monkeypatch.setattr(vf, "optional_import", lambda *_a, **_k: DummyModule)
    wave = np.ones(640, dtype=np.float32)  # enough for 2x 20ms frames at 16k
    ratio = vf.compute_voiced_ratio(wave, 16000, vad_mode=2)
    assert ratio is not None
    assert pytest.approx(0.5, rel=1e-6) == ratio


def test_compute_vad_runs_builds_voiced_and_silence_runs(monkeypatch) -> None:
    states = iter([True, True, False, True])

    class DummyVad:
        def __init__(self, _mode: int) -> None:
            pass

        def is_speech(self, _frame, _sr: int) -> bool:
            return next(states)

    class DummyModule:
        Vad = DummyVad

    monkeypatch.setattr(vf, "optional_import", lambda *_a, **_k: DummyModule)
    wave = np.ones(1280, dtype=np.float32)  # 4 frames at 16k
    ratio, voiced_runs, silence_runs = vf.compute_vad_runs(wave, 16000, vad_mode=0)
    assert ratio is not None and pytest.approx(0.75, rel=1e-6) == ratio
    assert voiced_runs == [0.04, 0.02]
    assert silence_runs == [0.02]


def test_compute_pitch_stats_returns_none_without_librosa(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ImportError("missing")

    monkeypatch.setattr(vf, "optional_import", _raise)
    out = vf.compute_pitch_stats(np.ones(100, dtype=np.float32), 16000, max_seconds=1.0)
    assert out == (None, None, None)


def test_compute_speech_rate_wps_edge_cases() -> None:
    assert vf.compute_speech_rate_wps("one two", 0.0) is None
    assert vf.compute_speech_rate_wps("", 2.0) == 0.0
    assert pytest.approx(1.5, rel=1e-6) == vf.compute_speech_rate_wps(
        "one two three", 2.0
    )


def test_extract_egemaps_filters_to_canonical_float_values(monkeypatch) -> None:
    class DummyRow:
        def to_dict(self):
            return {
                "jitterLocal_sma3nz_amean": "0.1",
                "loudness_sma3_amean": 12,
                "unknown": 999,
            }

    class DummyDf:
        def __len__(self):
            return 1

        class _ILoc:
            def __getitem__(self, _idx):
                return DummyRow()

        iloc = _ILoc()

    class DummyExtractor:
        def process_signal(self, _wave, _sr):
            return DummyDf()

    monkeypatch.setattr(vf, "build_opensmile_extractor", lambda: DummyExtractor())
    out = vf.extract_egemaps(np.ones(10, dtype=np.float32), 16000)
    assert out["jitter"] == pytest.approx(0.1)
    assert out["loudness"] == pytest.approx(12.0)
    assert "unknown" not in out
