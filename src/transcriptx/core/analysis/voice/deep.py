from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from transcriptx.core.utils.lazy_imports import optional_import  # type: ignore[import-untyped]

_PIPELINE: Any | None = None
_PIPELINE_MODEL: str | None = None


def _get_audio_cls_pipeline(model_name: str) -> Any:
    """
    Lazy-load a transformers audio-classification pipeline.

    We cache the pipeline instance for the duration of the process.
    """
    global _PIPELINE, _PIPELINE_MODEL
    if _PIPELINE is not None and _PIPELINE_MODEL == model_name:
        return _PIPELINE

    transformers = optional_import(
        "transformers",
        "deep-mode voice emotion inference",
        "emotion",
        auto_install=True,
    )
    pipeline = getattr(transformers, "pipeline", None)
    if pipeline is None:
        raise ImportError("transformers.pipeline is unavailable")

    # CPU-first by default; users can override via env if needed.
    _PIPELINE = pipeline("audio-classification", model=model_name)
    _PIPELINE_MODEL = model_name
    return _PIPELINE


def _emotion_to_valence(label: str) -> float | None:
    """
    Map common emotion labels to a coarse valence sign in [-1, 1].

    This is intentionally heuristic; we treat it as ranking assistance only.
    """
    if not label:
        return None
    l = label.strip().lower()

    # Common label sets across SER models
    if "joy" in l or "happy" in l:
        return 1.0
    if "neutral" in l:
        return 0.0
    if "sad" in l:
        return -1.0
    if "anger" in l or "angry" in l:
        return -0.9
    if "fear" in l:
        return -0.7
    if "disgust" in l:
        return -0.8
    if "surprise" in l:
        return 0.3
    return None


def infer_deep_emotion_and_valence(
    wave: np.ndarray,
    sample_rate: int,
    *,
    model_name: str,
    max_seconds: float,
) -> Dict[str, Any]:
    """
    Best-effort deep-mode inference.

    Returns a dict containing:
    - deep_emotion_label: str | None
    - deep_emotion_score: float | None
    - valence_raw: float | None
    - valence_method: "deep_model" | "none"
    """
    if wave is None or len(wave) == 0:
        return {
            "deep_emotion_label": None,
            "deep_emotion_score": None,
            "valence_raw": None,
            "valence_method": "none",
        }

    # Trim to guard runtime
    max_len = int(max(0.0, float(max_seconds)) * int(sample_rate))
    if max_len > 0 and len(wave) > max_len:
        wave = wave[:max_len]

    pipe = _get_audio_cls_pipeline(model_name)

    # transformers pipelines accept either a dict {array, sampling_rate} or kwargs.
    outputs: List[Dict[str, Any]]
    try:
        outputs = pipe(
            {
                "array": np.asarray(wave, dtype=np.float32),
                "sampling_rate": int(sample_rate),
            }
        )
    except Exception:
        outputs = pipe(
            np.asarray(wave, dtype=np.float32), sampling_rate=int(sample_rate)
        )

    if not outputs:
        return {
            "deep_emotion_label": None,
            "deep_emotion_score": None,
            "valence_raw": None,
            "valence_method": "none",
        }

    best = max(outputs, key=lambda x: float(x.get("score", 0.0) or 0.0))
    label = str(best.get("label") or "")
    score = float(best.get("score", 0.0) or 0.0)

    base_valence = _emotion_to_valence(label)
    if base_valence is None:
        valence = None
        method = "none"
    else:
        # Confidence-weighted coarse valence proxy
        valence = float(base_valence) * float(0.5 + 0.5 * max(0.0, min(1.0, score)))
        method = "deep_model"

    return {
        "deep_emotion_label": label or None,
        "deep_emotion_score": score if label else None,
        "valence_raw": valence,
        "valence_method": method,
    }
