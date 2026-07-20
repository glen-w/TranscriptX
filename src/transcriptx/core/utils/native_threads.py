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


@contextmanager
def limited_native_threads(n: int = 1) -> Iterator[None]:
    """Pin BLAS/OpenMP threads for the duration of a native fit.

    Oversubscription has been observed to hang BERTopic ``fit_transform``
    indefinitely. Only overrides keys for the call; restores prior values
    afterward.
    """
    threads = max(1, int(n))
    previous = {key: os.environ.get(key) for key in _NATIVE_THREAD_ENV_KEYS}
    try:
        for key in _NATIVE_THREAD_ENV_KEYS:
            os.environ[key] = str(threads)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
