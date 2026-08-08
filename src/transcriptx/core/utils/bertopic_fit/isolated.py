"""Isolate BERTopic ``fit_transform`` in a fresh subprocess.

On macOS host Python, BERTopic/UMAP/HDBSCAN can still SIGSEGV after a long
in-process pipeline (OpenMP/Numba state from prior modules) even when reduction
backends are pinned to ``n_jobs=1``. Running the fit in a spawned interpreter
keeps the parent pipeline alive and turns a native crash into a soft module
failure.

Lives under ``core.utils`` (not ``core.analysis``) because the parent must
write temp IPC payloads and pin child ``os.environ`` — operations forbidden in
analysis modules by audit guardrails.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class IsolatedFitResult:
    ok: bool
    topic_assignments: List[int]
    topic_probs: Any
    topics: List[Dict[str, Any]]
    duration_seconds: float
    error: Optional[str] = None
    exit_code: Optional[int] = None


def _cfg_snapshot(bertopic_cfg: Any) -> Dict[str, Any]:
    if bertopic_cfg is None:
        return {}
    keys = (
        "embedding_model",
        "min_topic_size",
        "nr_topics",
        "top_n_words",
        "label_words",
        "calculate_probabilities",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        if hasattr(bertopic_cfg, key):
            out[key] = getattr(bertopic_cfg, key)
    return out


def fit_bertopic_isolated(
    texts: Sequence[str],
    bertopic_cfg: Any,
    *,
    timeout_seconds: Optional[float] = None,
) -> IsolatedFitResult:
    """Fit BERTopic in a child process; return serializable topic artifacts."""
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="tx_bertopic_fit_") as tmp:
        tmp_path = Path(tmp)
        payload_path = tmp_path / "payload.json"
        result_path = tmp_path / "result.json"
        payload = {
            "texts": list(texts),
            "cfg": _cfg_snapshot(bertopic_cfg),
        }
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        env = os.environ.copy()
        # Fresh process: pin natives before any import in the child.
        env.setdefault("TOKENIZERS_PARALLELISM", "false")
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("MKL_NUM_THREADS", "1")
        env.setdefault("OPENBLAS_NUM_THREADS", "1")
        env.setdefault("NUMBA_NUM_THREADS", "1")
        env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
        # Prefer live src/ over a stale installed egg when developing.
        # isolated.py lives at src/transcriptx/core/utils/bertopic_fit/
        src_root = str(Path(__file__).resolve().parents[4])
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            src_root if not existing else f"{src_root}{os.pathsep}{existing}"
        )

        cmd = [
            sys.executable,
            "-m",
            "transcriptx.core.utils.bertopic_fit.worker",
            str(payload_path),
            str(result_path),
        ]
        try:
            completed = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=(
                    None
                    if not timeout_seconds or timeout_seconds <= 0
                    else float(timeout_seconds)
                ),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return IsolatedFitResult(
                ok=False,
                topic_assignments=[],
                topic_probs=None,
                topics=[],
                duration_seconds=time.perf_counter() - started,
                error="bertopic_fit_timeout",
                exit_code=None,
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            detail = detail[-800:] if detail else ""
            # 128+N => signal N on POSIX (139 = SIGSEGV).
            signal_hint = ""
            if completed.returncode < 0:
                signal_hint = f" signal={-completed.returncode}"
            elif completed.returncode >= 128:
                signal_hint = f" signal={completed.returncode - 128}"
            return IsolatedFitResult(
                ok=False,
                topic_assignments=[],
                topic_probs=None,
                topics=[],
                duration_seconds=time.perf_counter() - started,
                error=(
                    f"bertopic_native_crash:exit={completed.returncode}{signal_hint}"
                    + (f":{detail}" if detail else "")
                ),
                exit_code=completed.returncode,
            )

        if not result_path.exists():
            return IsolatedFitResult(
                ok=False,
                topic_assignments=[],
                topic_probs=None,
                topics=[],
                duration_seconds=time.perf_counter() - started,
                error="bertopic_fit_missing_result",
                exit_code=completed.returncode,
            )

        raw = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or not raw.get("ok"):
            return IsolatedFitResult(
                ok=False,
                topic_assignments=[],
                topic_probs=None,
                topics=[],
                duration_seconds=time.perf_counter() - started,
                error=str((raw or {}).get("error") or "bertopic_fit_failed"),
                exit_code=completed.returncode,
            )

        return IsolatedFitResult(
            ok=True,
            topic_assignments=[int(x) for x in (raw.get("topic_assignments") or [])],
            topic_probs=raw.get("topic_probs"),
            topics=list(raw.get("topics") or []),
            duration_seconds=float(
                raw.get("duration_seconds") or (time.perf_counter() - started)
            ),
            error=None,
            exit_code=0,
        )
