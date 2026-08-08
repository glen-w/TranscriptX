"""CLI entry for isolated BERTopic fits (``python -m ...bertopic_fit.worker``)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List


def _serialize_probs(topic_probs: Any) -> Any:
    if topic_probs is None:
        return None
    try:
        import numpy as np

        if isinstance(topic_probs, np.ndarray):
            return topic_probs.tolist()
    except Exception:
        pass
    if isinstance(topic_probs, list):
        out: List[Any] = []
        for row in topic_probs:
            if row is None:
                out.append(None)
                continue
            try:
                out.append([float(x) for x in row])
            except Exception:
                out.append(None)
        return out
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: worker <payload.json> <result.json>", file=sys.stderr)
        return 2

    payload_path = Path(args[0])
    result_path = Path(args[1])

    # Pin before importing BERTopic/UMAP/Numba (pool size is process-sticky).
    from transcriptx.core.utils.native_threads import ensure_native_thread_env_defaults

    ensure_native_thread_env_defaults()

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        texts = list(payload.get("texts") or [])
        cfg = SimpleNamespace(**dict(payload.get("cfg") or {}))

        from bertopic import BERTopic

        from transcriptx.core.analysis.bertopic.runtime import (
            build_model_kwargs,
            limited_native_threads,
        )
        from transcriptx.core.analysis.bertopic.utils import build_topic_objects

        model_kwargs = build_model_kwargs(cfg, threadsafe_reduction=True)
        started = time.perf_counter()
        with limited_native_threads(1):
            model = BERTopic(verbose=False, **model_kwargs)
            topic_assignments, topic_probs = model.fit_transform(texts)
        duration = time.perf_counter() - started

        top_n_words = int(getattr(cfg, "top_n_words", 10) or 10)
        label_words = int(getattr(cfg, "label_words", 3) or 3)
        topics = build_topic_objects(
            model,
            top_n_words=top_n_words,
            label_words=label_words,
            include_outlier=any(int(t) == -1 for t in topic_assignments),
        )
        result: Dict[str, Any] = {
            "ok": True,
            "topic_assignments": [int(t) for t in topic_assignments],
            "topic_probs": _serialize_probs(topic_probs),
            "topics": topics,
            "duration_seconds": duration,
        }
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return 0
    except Exception as exc:  # noqa: BLE001 — worker must always emit a result file
        result_path.write_text(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}),
            encoding="utf-8",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
