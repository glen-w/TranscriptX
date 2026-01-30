from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.utils.lazy_imports import optional_import  # type: ignore[import-untyped]
from transcriptx.core.utils.paths import DATA_DIR  # type: ignore[import-untyped]


def get_voice_cache_root() -> Path:
    root = Path(DATA_DIR) / "cache" / "voice"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_jsonl(df: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            record: dict[str, Any] = {}
            for col in df.columns:
                val = row[col]
                if val is None:
                    record[col] = None
                else:
                    # Convert numpy scalars to Python types where possible
                    try:
                        if hasattr(val, "item"):
                            val = val.item()
                    except Exception:
                        pass
                    record[col] = val
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path):  # -> pandas.DataFrame
    pd = optional_import("pandas", "voice feature tables")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def save_cache_meta(path: Path, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def load_cache_meta(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def save_voice_features(
    df: Any,
    *,
    core_path: Path,
    egemaps_path: Path | None,
    store_parquet_mode: str,
) -> dict[str, str | None]:
    """
    Save voice features to disk.

    - If store_parquet_mode is "on": require parquet support.
    - If "auto": attempt parquet, else fall back to JSONL.
    - If "off": write JSONL.
    """

    # Split into core vs egemaps columns if desired
    eg_cols = [c for c in df.columns if isinstance(c, str) and c.startswith("eg_")]
    core_cols = [c for c in df.columns if c not in eg_cols]
    core_df = df[core_cols].copy() if core_cols else df.copy()
    eg_df = df[["segment_id"] + eg_cols].copy() if eg_cols else None

    def _write_parquet(frame: Any, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)

    saved: dict[str, str | None] = {"core": None, "egemaps": None}
    mode = (store_parquet_mode or "auto").lower()

    if mode not in {"auto", "on", "off"}:
        mode = "auto"

    if mode in {"auto", "on"}:
        try:
            _write_parquet(core_df, core_path.with_suffix(".parquet"))
            saved["core"] = str(core_path.with_suffix(".parquet"))
            if egemaps_path is not None and eg_df is not None:
                _write_parquet(eg_df, egemaps_path.with_suffix(".parquet"))
                saved["egemaps"] = str(egemaps_path.with_suffix(".parquet"))
            return saved
        except Exception:
            if mode == "on":
                raise
            # Fall back to JSONL

    _write_jsonl(core_df, core_path.with_suffix(".jsonl"))
    saved["core"] = str(core_path.with_suffix(".jsonl"))
    if egemaps_path is not None and eg_df is not None:
        _write_jsonl(eg_df, egemaps_path.with_suffix(".jsonl"))
        saved["egemaps"] = str(egemaps_path.with_suffix(".jsonl"))
    return saved


def load_voice_features(
    *,
    core_path: Path,
    egemaps_path: Path | None,
):  # -> pandas.DataFrame
    """
    Load voice features from core + optional egemaps files.

    The loader detects parquet vs jsonl by file extension and presence.
    """

    pd = optional_import("pandas", "voice feature tables")

    def _load_one(path: Path):  # -> pandas.DataFrame
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".jsonl":
            return _read_jsonl(path)
        # Try parquet then jsonl
        if path.with_suffix(".parquet").exists():
            return pd.read_parquet(path.with_suffix(".parquet"))
        return _read_jsonl(path.with_suffix(".jsonl"))

    core_df = _load_one(core_path)
    if egemaps_path is None:
        return core_df
    # If no egemaps file exists, just return core
    if not egemaps_path.with_suffix(".parquet").exists() and not egemaps_path.with_suffix(
        ".jsonl"
    ).exists():
        return core_df
    eg_df = _load_one(egemaps_path)
    if "segment_id" in core_df.columns and "segment_id" in eg_df.columns:
        return core_df.merge(eg_df, on="segment_id", how="left")
    return core_df

