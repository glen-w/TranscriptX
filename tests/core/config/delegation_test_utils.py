"""Shared helpers for Batch 5 runtime delegation tests."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterator

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
    assert len(PYDANTIC_REGISTRY_PILOTS) == 41
    assert len(pilot_keys) == 598
    assert len(baseline) == 10
    assert len(reg) == 608


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
            "asdict": asdict(getattr(AnalysisConfig(), subtree)),
            "to_dict": TranscriptXConfig().to_dict()["analysis"][subtree],
        }
    assert actual == expected


def assert_is_dataclass_subtree(subtree: str) -> None:
    assert is_dataclass(type(getattr(AnalysisConfig(), subtree)))
