"""Offline unit tests for voice schema + cache helpers (no real audio)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from transcriptx.core.analysis.voice import cache as voice_cache
from transcriptx.core.analysis.voice.schema import (
    VoiceFeatureRow,
    VoiceFeatureTable,
    resolve_segment_id,
)


@pytest.mark.unit
def test_resolve_segment_id_delegates_to_corrections_helper() -> None:
    seg = {"start": 0.0, "end": 1.0, "speaker": "Alice", "text": "hello"}
    sid = resolve_segment_id(seg, "tk")
    assert isinstance(sid, str)
    assert sid


@pytest.mark.unit
def test_voice_feature_table_roundtrip_expands_eg_columns() -> None:
    table = VoiceFeatureTable(
        rows=[
            VoiceFeatureRow(
                segment_id="s1",
                speaker="Alice",
                start_s=0.0,
                end_s=1.0,
                duration_s=1.0,
                rms_db=-20.0,
                eg={"hnr_db": 12.5, "jitter": 0.01},
            )
        ]
    )
    frame = table.to_frame()
    assert "eg_hnr_db" in frame.columns
    assert float(frame.iloc[0]["eg_hnr_db"]) == pytest.approx(12.5)

    restored = VoiceFeatureTable.from_frame(frame)
    assert len(restored.rows) == 1
    assert restored.rows[0].segment_id == "s1"
    assert restored.rows[0].eg["hnr_db"] == pytest.approx(12.5)
    assert restored.rows[0].eg["jitter"] == pytest.approx(0.01)


@pytest.mark.unit
def test_cache_meta_roundtrip_and_corrupt(tmp_path: Path) -> None:
    meta_path = tmp_path / "meta.json"
    assert voice_cache.load_cache_meta(meta_path) is None

    voice_cache.save_cache_meta(meta_path, {"hash": "abc", "n": 2})
    loaded = voice_cache.load_cache_meta(meta_path)
    assert loaded == {"hash": "abc", "n": 2}

    meta_path.write_text("not-json", encoding="utf-8")
    assert voice_cache.load_cache_meta(meta_path) is None

    meta_path.write_text("[1, 2]", encoding="utf-8")
    assert voice_cache.load_cache_meta(meta_path) is None


@pytest.mark.unit
def test_get_voice_cache_root_uses_data_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(voice_cache, "DATA_DIR", tmp_path)
    root = voice_cache.get_voice_cache_root()
    assert root == tmp_path / "cache" / "voice"
    assert root.is_dir()


@pytest.mark.unit
def test_save_voice_features_jsonl_off_mode(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "segment_id": "s1",
                "speaker": "A",
                "rms_db": -18.0,
                "eg_hnr_db": 10.0,
            }
        ]
    )
    core = tmp_path / "core"
    eg = tmp_path / "eg"
    saved = voice_cache.save_voice_features(
        df,
        core_path=core,
        egemaps_path=eg,
        store_parquet_mode="off",
    )
    assert saved["core"] and saved["core"].endswith(".jsonl")
    assert saved["egemaps"] and saved["egemaps"].endswith(".jsonl")
    assert Path(saved["core"]).exists()
    assert Path(saved["egemaps"]).exists()

    loaded = voice_cache.load_voice_features(
        core_path=Path(saved["core"]),
        egemaps_path=Path(saved["egemaps"]),
    )
    assert "eg_hnr_db" in loaded.columns
    assert loaded.iloc[0]["segment_id"] == "s1"


@pytest.mark.unit
def test_save_voice_features_on_mode_raises_without_parquet(tmp_path: Path) -> None:
    df = pd.DataFrame([{"segment_id": "s1", "rms_db": 1.0}])
    core = tmp_path / "core"

    class _BoomFrame:
        columns = df.columns

        def __getitem__(self, _cols):
            return self

        def copy(self):
            return self

        def to_parquet(self, *_a, **_k):
            raise OSError("no parquet")

    with patch.object(voice_cache, "optional_import", return_value=pd):
        with pytest.raises(OSError, match="no parquet"):
            voice_cache.save_voice_features(
                _BoomFrame(),
                core_path=core,
                egemaps_path=None,
                store_parquet_mode="on",
            )


@pytest.mark.unit
def test_npvi_varco_zero_denom_and_nonpositive_mean() -> None:
    from transcriptx.core.analysis.voice.rhythm import npvi, varco

    assert npvi([0.0, 0.0, 0.0]) is None
    assert varco([-1.0, -2.0]) is None
