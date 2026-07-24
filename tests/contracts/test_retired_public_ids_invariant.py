"""Invariant: retired public module / schema ids must not appear in live surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path

from transcriptx.core.config.models.ui_presets import AnalysisUiPresetsModel
from transcriptx.core.pipeline.module_registry import (
    get_default_modules,
    get_module_info,
)
from transcriptx.core.pipeline.retired_public_ids import (
    OBSOLETE_PUBLIC_SCHEMA_IDS,
    PUBLIC_MODULE_VN_SUFFIX_RE,
    RETIRED_PUBLIC_MODULE_IDS,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VN_RE = re.compile(PUBLIC_MODULE_VN_SUFFIX_RE)


def _collect_strings(obj: object) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                out.append(k)
            out.extend(_collect_strings(v))
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            out.extend(_collect_strings(item))
    return out


def test_registry_rejects_retired_and_vn_module_ids() -> None:
    defaults = get_default_modules(include_legacy=False)
    for retired in RETIRED_PUBLIC_MODULE_IDS:
        assert get_module_info(retired) is None
        assert retired not in defaults
    for module_id in defaults:
        assert not _VN_RE.match(module_id), module_id
        assert module_id not in RETIRED_PUBLIC_MODULE_IDS


def test_balanced_preset_rejects_retired_module_ids() -> None:
    presets = AnalysisUiPresetsModel()
    for policy in (presets.quick, presets.balanced, presets.thorough):
        for field in ("heavy_module_ids", "llm_module_ids"):
            values = getattr(policy, field) or []
            for retired in RETIRED_PUBLIC_MODULE_IDS:
                assert retired not in values
            for value in values:
                assert not _VN_RE.match(value), value


def test_live_fixtures_reject_retired_ids() -> None:
    fixture_roots = [
        _REPO_ROOT / "tests" / "core" / "config" / "fixtures",
        _REPO_ROOT / "tests" / "fixtures" / "module_registry",
        _REPO_ROOT / "docs" / "generated",
    ]
    banned = RETIRED_PUBLIC_MODULE_IDS | OBSOLETE_PUBLIC_SCHEMA_IDS
    offenders: list[str] = []
    for root in fixture_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            # Historical golden filenames may mention v2; content must not.
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            for value in _collect_strings(data):
                if value in banned:
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{value}")
                if _VN_RE.match(value) and value.startswith("semantic_similarity"):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{value}")
    assert not offenders, "retired/obsolete ids in fixtures:\n" + "\n".join(offenders)


def test_aggregation_registry_rejects_retired_module_ids() -> None:
    from transcriptx.core.analysis.aggregation import registry as agg_registry

    text = Path(agg_registry.__file__).read_text(encoding="utf-8")
    for retired in RETIRED_PUBLIC_MODULE_IDS:
        assert retired not in text, retired
