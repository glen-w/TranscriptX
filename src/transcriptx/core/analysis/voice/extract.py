from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import get_logger  # type: ignore[import-untyped]
from transcriptx.core.utils.artifact_writer import write_json

from .audio_io import (
    compute_audio_fingerprint,
    ensure_cached_wav,
    read_audio_segment,
    resolve_audio_path,
)
from .cache import (
    get_voice_cache_root,
    load_cache_meta,
    save_cache_meta,
    save_voice_features,
)
from .features import (
    compute_pitch_stats,
    compute_rms_db,
    compute_speech_rate_wps,
    compute_vad_runs,
    extract_egemaps,
)
from .schema import resolve_segment_id

logger = get_logger()


def compute_segments_timing_hash(
    segments: List[Dict[str, Any]], transcript_key: str
) -> str:
    items: list[tuple[str, float, float, str]] = []
    for seg in segments:
        seg_id = resolve_segment_id(seg, transcript_key)
        start = float(seg.get("start", seg.get("start_time", 0.0)) or 0.0)
        end = float(seg.get("end", seg.get("end_time", start)) or start)
        speaker = str(seg.get("speaker") or "")
        items.append((seg_id, start, end, speaker))
    payload = json.dumps(
        items, ensure_ascii=True, separators=(",", ":"), sort_keys=False
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_voice_config_hash(config: Any) -> str:
    voice = getattr(getattr(config, "analysis", None), "voice", None)
    # Only hash cache-affecting knobs.
    payload = {
        "sample_rate": getattr(voice, "sample_rate", 16000),
        "vad_mode": getattr(voice, "vad_mode", 2),
        "pad_s": getattr(voice, "pad_s", 0.15),
        "max_seconds_for_pitch": getattr(voice, "max_seconds_for_pitch", 20.0),
        "egemaps_enabled": getattr(voice, "egemaps_enabled", True),
        "deep_mode": getattr(voice, "deep_mode", False),
        "deep_model_name": getattr(
            voice, "deep_model_name", "superb/wav2vec2-base-superb-er"
        ),
        "deep_max_seconds": getattr(voice, "deep_max_seconds", 12.0),
        "store_parquet": getattr(voice, "store_parquet", "auto"),
        "strict_audio_hash": getattr(voice, "strict_audio_hash", False),
        "max_segments_considered": getattr(voice, "max_segments_considered", None),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        # Try hardlink first (fast, no duplication)
        dst.hardlink_to(src)
        return
    except Exception:
        pass
    shutil.copyfile(src, dst)


def load_or_compute_voice_features(
    *,
    context: Any,
    output_service: Any,
) -> Dict[str, Any]:
    """
    Compute (or reuse cached) per-segment voice features.

    Returns a *locator payload* used by downstream modules.
    """
    started = time.time()
    cfg = get_config()
    voice_cfg = getattr(getattr(cfg, "analysis", None), "voice", None)
    if voice_cfg is None or not getattr(voice_cfg, "enabled", True):
        return {"status": "skipped", "skipped_reason": "disabled"}

    segments = context.get_segments()
    transcript_key = context.get_transcript_key()
    output_dir = context.get_transcript_dir()

    # Guard: timestamps
    if not all(("start" in s and "end" in s) for s in segments):
        return {"status": "skipped", "skipped_reason": "missing_timestamps"}

    audio_path = resolve_audio_path(
        transcript_path=context.transcript_path, output_dir=output_dir
    )
    if not audio_path:
        return {"status": "skipped", "skipped_reason": "no_audio"}

    sample_rate = int(getattr(voice_cfg, "sample_rate", 16000))
    vad_mode = int(getattr(voice_cfg, "vad_mode", 2))
    pad_s = float(getattr(voice_cfg, "pad_s", 0.15))
    max_pitch = float(getattr(voice_cfg, "max_seconds_for_pitch", 20.0))
    egemaps_enabled = bool(getattr(voice_cfg, "egemaps_enabled", True))
    deep_mode = bool(getattr(voice_cfg, "deep_mode", False))
    deep_model_name = str(
        getattr(voice_cfg, "deep_model_name", "superb/wav2vec2-base-superb-er")
    )
    deep_max_seconds = float(getattr(voice_cfg, "deep_max_seconds", 12.0))
    store_parquet = str(getattr(voice_cfg, "store_parquet", "auto"))
    strict_audio_hash = bool(getattr(voice_cfg, "strict_audio_hash", False))
    max_segments_considered = getattr(voice_cfg, "max_segments_considered", None)

    audio_fingerprint = compute_audio_fingerprint(audio_path, strict=strict_audio_hash)
    segments_hash = compute_segments_timing_hash(segments, transcript_key)
    voice_config_hash = compute_voice_config_hash(cfg)

    cache_root = (
        get_voice_cache_root()
        / transcript_key.replace(":", "_")
        / audio_fingerprint.replace(":", "_")
        / segments_hash.replace(":", "_")
        / voice_config_hash.replace(":", "_")
    )
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_meta_path = cache_root / "voice_features_cache_meta.json"
    cache_meta = load_cache_meta(cache_meta_path)

    base_name = output_service.base_name
    output_structure = output_service.get_output_structure()
    run_dir = Path(output_structure.global_data_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    run_core_base = run_dir / f"{base_name}_voice_features_core"
    run_eg_base = run_dir / f"{base_name}_voice_features_egemaps"

    # Determine cached file paths (either parquet or jsonl)
    cached_core = cache_root / "voice_features_core"
    cached_eg = cache_root / "voice_features_egemaps"

    def _existing_variant(base: Path) -> Path | None:
        if base.with_suffix(".parquet").exists():
            return base.with_suffix(".parquet")
        if base.with_suffix(".jsonl").exists():
            return base.with_suffix(".jsonl")
        return None

    cached_core_path = _existing_variant(cached_core)
    cached_eg_path = _existing_variant(cached_eg)
    cached_vad_runs = cache_root / "voice_vad_runs.json"
    cache_hit = bool(cache_meta) and cached_core_path is not None

    if cache_hit and cached_core_path is not None:
        # Copy cached artifacts into run directory (so manifest includes them)
        run_core_path: Path = run_core_base.with_suffix(cached_core_path.suffix)
        _copy_if_needed(cached_core_path, run_core_path)
        run_eg_path: Path | None = None
        if cached_eg_path is not None:
            run_eg_path = run_eg_base.with_suffix(cached_eg_path.suffix)
            _copy_if_needed(cached_eg_path, run_eg_path)
        run_vad_runs_path: Path | None = None
        if cached_vad_runs.exists():
            run_vad_runs_path = run_dir / f"{base_name}_voice_vad_runs.json"
            _copy_if_needed(cached_vad_runs, run_vad_runs_path)
        # Also copy meta
        run_meta_path = run_dir / f"{base_name}_voice_features_cache_meta.json"
        _copy_if_needed(cache_meta_path, run_meta_path)
        return {
            "status": "ok",
            "skipped_reason": None,
            "voice_feature_core_path": str(run_core_path),
            "voice_feature_egemaps_path": str(run_eg_path) if run_eg_path else None,
            "voice_feature_vad_runs_path": (
                str(run_vad_runs_path) if run_vad_runs_path else None
            ),
            "cache_meta_path": str(run_meta_path),
            "meta": {
                "audio_path": audio_path,
                "audio_fingerprint": audio_fingerprint,
                "fingerprint_method": (
                    "content_sha256" if strict_audio_hash else "fast_size_mtime"
                ),
                "segments_hash": segments_hash,
                "voice_config_hash": voice_config_hash,
                "cache_hit": True,
                "row_count": (
                    cache_meta.get("row_count")
                    if isinstance(cache_meta, dict)
                    else None
                ),
                "duration_seconds": time.time() - started,
            },
        }

    # Cache miss: compute
    # Limit segments if configured (defensive for huge transcripts)
    if isinstance(max_segments_considered, int) and max_segments_considered > 0:
        segments_to_use = segments[:max_segments_considered]
    else:
        segments_to_use = segments

    cache_audio_dir = cache_root / "audio"
    seekable_path, decode_meta = ensure_cached_wav(
        audio_path, cache_dir=cache_audio_dir, sample_rate=sample_rate
    )

    pd = __import__("pandas")
    rows: list[dict[str, Any]] = []
    vad_runs: dict[str, dict[str, list[float]]] = {}
    deep_available = False
    deep_errors: list[str] = []
    for idx, seg in enumerate(segments_to_use):
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start) or start)
        if end <= start:
            continue
        speaker = seg.get("speaker")
        seg_id = resolve_segment_id(seg, transcript_key)
        duration = float(end - start)
        text = seg.get("text", "") or ""

        try:
            wave = read_audio_segment(
                wav_path=seekable_path,
                start_s=start,
                end_s=end,
                sample_rate=sample_rate,
                pad_s=pad_s,
            )
        except Exception:
            continue

        rms_db = compute_rms_db(wave)
        voiced_ratio, voiced_runs, silence_runs = compute_vad_runs(
            wave, sample_rate, vad_mode
        )
        vad_runs[str(seg_id)] = {
            "voiced_runs_s": voiced_runs,
            "silence_runs_s": silence_runs,
        }
        f0_mean, f0_std, f0_range = compute_pitch_stats(
            wave, sample_rate, max_seconds=max_pitch
        )
        speech_rate = compute_speech_rate_wps(text, duration)
        eg = extract_egemaps(wave, sample_rate) if egemaps_enabled else {}

        deep_payload: dict[str, Any] = {}
        if deep_mode:
            try:
                from .deep import infer_deep_emotion_and_valence

                deep_payload = infer_deep_emotion_and_valence(
                    wave,
                    sample_rate,
                    model_name=deep_model_name,
                    max_seconds=deep_max_seconds,
                )
                deep_available = True
            except Exception as e:
                # Best-effort: fall back silently to classic proxies
                deep_errors.append(str(e)[:200])
                deep_payload = {}

        row: dict[str, Any] = {
            "segment_idx": idx,
            "segment_id": seg_id,
            "speaker": speaker,
            "start_s": start,
            "end_s": end,
            "duration_s": duration,
            "voiced_ratio": voiced_ratio,
            "rms_db": rms_db,
            "f0_mean_hz": f0_mean,
            "f0_std_hz": f0_std,
            "f0_range_semitones": f0_range,
            "speech_rate_wps": speech_rate,
        }
        for k, v in eg.items():
            row[f"eg_{k}"] = v
        # Deep-mode (optional) columns live in core table (non eg_* prefix)
        for k, v in (deep_payload or {}).items():
            row[k] = v
        rows.append(row)

    df = pd.DataFrame(rows)

    # Save to stable cache (core + optional egemaps)
    saved_paths = save_voice_features(
        df,
        core_path=cached_core,
        egemaps_path=cached_eg if egemaps_enabled else None,
        store_parquet_mode=store_parquet,
    )
    if vad_runs:
        write_json(cached_vad_runs, vad_runs, indent=2, ensure_ascii=False)

    # Save cache meta
    meta = {
        "audio_path": audio_path,
        "audio_fingerprint": audio_fingerprint,
        "fingerprint_method": (
            "content_sha256" if strict_audio_hash else "fast_size_mtime"
        ),
        "segments_hash": segments_hash,
        "voice_config_hash": voice_config_hash,
        "cache_hit": False,
        "row_count": int(len(df)),
        "decode": decode_meta,
        "saved": saved_paths,
        "deep_mode": deep_mode,
        "deep_model_name": deep_model_name if deep_mode else None,
        "deep_available": deep_available if deep_mode else False,
        "deep_errors_sample": (deep_errors[:3] if deep_errors else []),
    }
    save_cache_meta(cache_meta_path, meta)

    # Copy cached artifacts into run directory
    core_saved = saved_paths.get("core")
    eg_saved = saved_paths.get("egemaps")
    cached_core_path2: Path | None = (
        Path(core_saved) if isinstance(core_saved, str) else None
    )
    cached_eg_path2: Path | None = Path(eg_saved) if isinstance(eg_saved, str) else None
    run_core_path2: Path | None = None
    run_eg_path2: Path | None = None
    if cached_core_path2 is not None:
        run_core_path2 = run_core_base.with_suffix(cached_core_path2.suffix)
        _copy_if_needed(cached_core_path2, run_core_path2)
    if cached_eg_path2 is not None:
        run_eg_path2 = run_eg_base.with_suffix(cached_eg_path2.suffix)
        _copy_if_needed(cached_eg_path2, run_eg_path2)
    run_meta_path = run_dir / f"{base_name}_voice_features_cache_meta.json"
    _copy_if_needed(cache_meta_path, run_meta_path)
    run_vad_runs_path: Path | None = None
    if cached_vad_runs.exists():
        run_vad_runs_path = run_dir / f"{base_name}_voice_vad_runs.json"
        _copy_if_needed(cached_vad_runs, run_vad_runs_path)

    return {
        "status": "ok",
        "skipped_reason": None,
        "voice_feature_core_path": str(run_core_path2) if run_core_path2 else None,
        "voice_feature_egemaps_path": str(run_eg_path2) if run_eg_path2 else None,
        "voice_feature_vad_runs_path": (
            str(run_vad_runs_path) if run_vad_runs_path else None
        ),
        "cache_meta_path": str(run_meta_path),
        "meta": {
            "audio_path": audio_path,
            "audio_fingerprint": audio_fingerprint,
            "fingerprint_method": (
                "content_sha256" if strict_audio_hash else "fast_size_mtime"
            ),
            "segments_hash": segments_hash,
            "voice_config_hash": voice_config_hash,
            "cache_hit": False,
            "row_count": int(len(df)),
            "duration_seconds": time.time() - started,
        },
    }
