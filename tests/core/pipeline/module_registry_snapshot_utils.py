"""Stable serialization helpers for module registry snapshot tests."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "module_registry"
    / "module_definitions_snapshot.json"
)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(_normalize_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(val) for key, val in value.items()}
    return value


def _normalize_module_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_value(spec)
    return dict(sorted(normalized.items()))


def normalize_module_definitions(raw: dict[str, dict]) -> dict[str, Any]:
    """Return JSON-compatible snapshot structure preserving module order."""
    return {
        "module_order": list(raw.keys()),
        "modules": {
            module_id: _normalize_module_spec(spec) for module_id, spec in raw.items()
        },
    }


def load_snapshot_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def observed_spec_keys(raw: dict[str, dict]) -> set[str]:
    keys: set[str] = set()
    for spec in raw.values():
        keys.update(spec.keys())
    return keys


def merge_fragments(*fragments: dict[str, dict]) -> dict[str, dict]:
    """Merge domain fragments, raising if any module id appears more than once."""
    merged: dict[str, dict] = {}
    for fragment in fragments:
        overlap = set(merged) & set(fragment)
        if overlap:
            raise AssertionError(
                f"duplicate module ids across fragments: {sorted(overlap)}"
            )
        merged.update(fragment)
    return merged
