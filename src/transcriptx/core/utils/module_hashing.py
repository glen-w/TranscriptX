"""
Module hashing utilities for cache keys.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Dict

def _hash_payload(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_module_source_hash(module_name: str) -> str:
    """Compute hash of a module's source file contents."""
    from transcriptx.core.pipeline.module_registry import get_module_function

    module_func = get_module_function(module_name)
    if module_func is None:
        return ""
    try:
        source_file = inspect.getsourcefile(module_func)
        if not source_file:
            return ""
        source_path = Path(source_file)
        return hashlib.sha256(source_path.read_bytes()).hexdigest()
    except Exception:
        return ""


def compute_module_config_hash(module_name: str, config_payload: Dict[str, Any]) -> str:
    """Compute hash of cache-affecting module configuration."""
    payload = {"module": module_name, "config": config_payload}
    return _hash_payload(payload)


def compute_pipeline_config_hash(config_payload: Dict[str, Any]) -> str:
    """Compute hash of pipeline-level configuration."""
    return _hash_payload(config_payload)
