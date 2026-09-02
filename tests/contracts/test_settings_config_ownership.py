"""Config ownership: Settings keys are Pydantic or an explicit baseline."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from transcriptx.core.config.pydantic_bridge import (
    all_pydantic_field_dotpaths,
    serialize_non_pydantic_registry_baseline,
)
from transcriptx.core.config.registry import build_registry
from transcriptx.core.utils.config.env_key_registry import INFRA_ENV_ALLOWLIST

FIXTURES = Path(__file__).resolve().parents[1] / "core" / "config" / "fixtures"

_THEME_C_TX_FLAGS = (
    "TX_SPEAKER_ID_WORKSPACE_COMPONENT",
    "TX_CORRECTIONS_WORKSPACE_COMPONENT",
    "TX_SID_CLIP_POLL",
)


@contextmanager
def _without_transcriptx_env() -> Iterator[None]:
    saved = {k: v for k, v in os.environ.items() if k.startswith("TRANSCRIPTX_")}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def test_theme_c_tx_flags_are_in_env_registry() -> None:
    for key in _THEME_C_TX_FLAGS:
        assert key in INFRA_ENV_ALLOWLIST, key


def test_env_example_documents_theme_c_tx_flags() -> None:
    env_example = (
        Path(__file__).resolve().parents[2] / ".env.example"
    ).read_text(encoding="utf-8")
    for key in _THEME_C_TX_FLAGS:
        assert key in env_example, key


def test_every_settings_registry_key_is_pydantic_or_explicit_baseline() -> None:
    """New Settings knobs must be Pydantic fields or added to the frozen baseline.

    ``non_pydantic_registry_baseline.json`` is the allowlist for remaining
    dataclass-backed keys. Do not add dataclass-only Settings fields.
    """
    baseline_path = FIXTURES / "non_pydantic_registry_baseline.json"
    baseline = set(json.loads(baseline_path.read_text(encoding="utf-8")))
    with _without_transcriptx_env():
        registry = build_registry()
        actual_non_pydantic = set(serialize_non_pydantic_registry_baseline(registry))
    pydantic_keys = all_pydantic_field_dotpaths()
    extra_dataclass = actual_non_pydantic - baseline
    missing_baseline = baseline - actual_non_pydantic
    leaked_into_pydantic = baseline & pydantic_keys
    assert not extra_dataclass, (
        "Settings keys without a Pydantic model or baseline entry: "
        f"{sorted(extra_dataclass)}"
    )
    assert not missing_baseline, (
        "Baseline keys no longer in the non-pydantic registry "
        f"(migrate golden): {sorted(missing_baseline)}"
    )
    assert not leaked_into_pydantic, (
        "Baseline keys are now Pydantic fields; remove them from the golden: "
        f"{sorted(leaked_into_pydantic)}"
    )
    assert set(registry) == pydantic_keys | actual_non_pydantic
