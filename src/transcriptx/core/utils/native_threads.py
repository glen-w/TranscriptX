"""Native BLAS/OpenMP thread pinning helpers.

Kept outside ``core.analysis`` so analysis modules stay free of ``os.environ``
access (see ``tests/unit/test_audit_guardrails.py``).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

_NATIVE_THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMBA_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)

# Defaults applied before Numba/UMAP first import (pool size is process-sticky).
_NATIVE_THREAD_ENV_DEFAULTS = (
    ("TOKENIZERS_PARALLELISM", "false"),
    ("OMP_NUM_THREADS", "1"),
    ("MKL_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
    ("NUMBA_NUM_THREADS", "1"),
    ("VECLIB_MAXIMUM_THREADS", "1"),
)


def ensure_native_thread_env_defaults() -> None:
    """Pin BLAS/OpenMP/Numba thread env vars when unset."""
    for key, value in _NATIVE_THREAD_ENV_DEFAULTS:
        os.environ.setdefault(key, value)


@contextmanager
def limited_native_threads(n: int = 1) -> Iterator[None]:
    """Pin BLAS/OpenMP threads for the duration of a native fit.

    Oversubscription has been observed to hang BERTopic ``fit_transform``
    indefinitely. Only overrides keys for the call; restores prior values
    afterward.

    ``NUMBA_NUM_THREADS`` is left unchanged when Numba's thread pool is already
    initialized — Numba raises if that env var changes after launch.
    """
    threads = max(1, int(n))
    keys = list(_NATIVE_THREAD_ENV_KEYS)
    try:
        from numba.np.ufunc import parallel as _numba_parallel

        if getattr(_numba_parallel, "_is_initialized", False):
            keys = [k for k in keys if k != "NUMBA_NUM_THREADS"]
    except Exception:
        pass

    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ[key] = str(threads)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
