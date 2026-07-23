"""Shared helpers for Batch 5 runtime delegation tests."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    serialize_non_pydantic_registry_baseline,
)
from transcriptx.core.config.registry import build_registry
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@contextmanager
def without_transcriptx_env() -> Iterator[None]:
    """Clear TRANSCRIPTX_* env vars for default-shape assertions.

    Importing path/config modules bootstraps repo ``.env`` into ``os.environ``,
    which otherwise contaminates ``TranscriptXConfig()`` default comparisons.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("TRANSCRIPTX_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def assert_ownership_invariant_unchanged() -> None:
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline = serialize_non_pydantic_registry_baseline(reg)
    assert len(PYDANTIC_REGISTRY_PILOTS) == 49
    assert len(pilot_keys) == 664
    assert len(baseline) == 16
    assert len(reg) == 680


def normalize_for_parity(obj: Any) -> Any:
    """Normalize values for dataclass↔model *defaults* comparison.

    Converts Enums to values and nested structures to comparable form.
    Production ``to_dict()`` must still preserve Python types (e.g. tuples);
    do not use this helper to drive snapshot conversion.
    """
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: normalize_for_parity(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {k: normalize_for_parity(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize_for_parity(v) for v in obj]
    if isinstance(obj, set):
        return sorted(
            (normalize_for_parity(v) for v in obj),
            key=lambda x: json.dumps(x, sort_keys=True, default=str),
        )
    return obj


def assert_normalized_defaults_parity(left: Any, right: Any) -> None:
    assert normalize_for_parity(left) == normalize_for_parity(right)


def assert_mutable_container_independence(factory: Callable[[], Any]) -> None:
    """Two fresh instances must not share mutable container object identity."""
    a = factory()
    b = factory()
    assert a is not b
    for f in fields(a):
        va = getattr(a, f.name)
        vb = getattr(b, f.name)
        if isinstance(va, (list, dict, set)) or (
            is_dataclass(va) and not isinstance(va, type)
        ):
            assert va is not vb, f"shared mutable identity for field {f.name!r}"


def assert_three_path_access(subtree: str, field: str, expected: Any) -> None:
    with without_transcriptx_env():
        ac = AnalysisConfig()
        cfg = TranscriptXConfig()
        assert getattr(getattr(ac, subtree), field) == expected
        assert getattr(getattr(cfg.analysis, subtree), field) == expected
        assert cfg.to_dict()["analysis"][subtree][field] == expected


def assert_subtree_shape_matches_pre_snapshot(subtree: str) -> None:
    expected = json.loads(
        (FIXTURES / f"delegation_shape_{subtree}_pre.json").read_text()
    )
    with without_transcriptx_env():
        actual = {
            "asdict": normalize_for_parity(asdict(getattr(AnalysisConfig(), subtree))),
            "to_dict": normalize_for_parity(
                TranscriptXConfig().to_dict()["analysis"][subtree]
            ),
        }
    assert actual == normalize_for_parity(expected)


def assert_is_dataclass_subtree(subtree: str) -> None:
    assert is_dataclass(type(getattr(AnalysisConfig(), subtree)))
