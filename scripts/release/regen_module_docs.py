#!/usr/bin/env python3
"""Regenerate module catalog + analysis-quality audit scaffold from the registry.

Maintainer tooling (0.9.5). Writes:
  - docs/generated/modules.md
  - docs/dev/analysis_quality_audit_scaffold.md

Usage (from repo root):
  python3 scripts/release/regen_module_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transcriptx.core.pipeline.module_specs import (  # noqa: E402
    MODULE_REGISTRY_ORDER,
    build_all_module_definitions,
)

MODULES_MD = ROOT / "docs" / "generated" / "modules.md"
AUDIT_SCAFFOLD = ROOT / "docs" / "dev" / "analysis_quality_audit_scaffold.md"


def _deps_cell(deps: list | tuple | None) -> str:
    if not deps:
        return "None"
    return ", ".join(str(d) for d in deps)


def render_modules_md(defs: dict[str, dict]) -> str:
    rows = []
    for mid in MODULE_REGISTRY_ORDER:
        spec = defs[mid]
        desc = str(spec.get("description") or "").replace("|", "\\|")
        cat = str(spec.get("category") or "")
        deps = _deps_cell(spec.get("dependencies"))
        tier = str(spec.get("determinism_tier") or "")
        rows.append(f"| {mid} | {desc} | {cat} | {deps} | {tier} |")
    body = "\n".join(rows)
    return f"""# Module Catalog

*This catalog is generated from the ModuleRegistry.*
*Regenerate: `python3 scripts/release/regen_module_docs.py` (or `make docs-gen`).*

## Available Modules

| Module | Description | Category | Dependencies | Determinism |
|--------|-------------|----------|--------------|-------------|
{body}

## Category Definitions

- **light**: Fast, minimal computation (< 1 second per transcript)
- **medium**: Moderate computation, may use ML models (1-10 seconds)
- **heavy**: Intensive computation, large models (10+ seconds)

## Determinism Tiers

- **T0**: Fully deterministic - same input always produces same output
- **T1**: Mostly deterministic - minor variations possible (e.g., floating point)
- **T2**: Non-deterministic - output depends on model initialization or randomness

## Related guides

- Local LLM modules: [runtime/llm.md](../runtime/llm.md)
- Lexical diversity: [runtime/lexical_diversity.md](../runtime/lexical_diversity.md)
- BERTopic optional module: [dev/bertopic_optional_module.md](../dev/bertopic_optional_module.md)
- Models / embedding env: [runtime/models.md](../runtime/models.md)
"""


def render_audit_scaffold(defs: dict[str, dict]) -> str:
    rows = []
    for mid in MODULE_REGISTRY_ORDER:
        spec = defs[mid]
        desc = str(spec.get("description") or "").replace("|", "\\|")
        cat = str(spec.get("category") or "")
        deps = _deps_cell(spec.get("dependencies"))
        tier = str(spec.get("determinism_tier") or "")
        rows.append(
            f"| `{mid}` | {desc} | {cat} | {deps} | {tier} | | | |"
        )
    body = "\n".join(rows)
    return f"""# Analysis quality audit scaffold (generated)

**Status:** machine scaffold from `MODULE_REGISTRY_ORDER` (**0.9.5**)  
**Do not hand-edit rows** — regenerate with `python3 scripts/release/regen_module_docs.py`.  
Human judgements (meaningfulness, recommendation, severity) live in empty columns below and in [analysis_quality_audit.md](analysis_quality_audit.md).

| Module id | Description | Category | Dependencies | Determinism | Recommendation | Severity | Notes |
|-----------|-------------|----------|--------------|-------------|----------------|----------|-------|
{body}
"""


def main() -> int:
    defs = build_all_module_definitions([])
    if set(defs) != set(MODULE_REGISTRY_ORDER):
        missing = set(MODULE_REGISTRY_ORDER) - set(defs)
        extra = set(defs) - set(MODULE_REGISTRY_ORDER)
        raise SystemExit(f"registry mismatch missing={sorted(missing)} extra={sorted(extra)}")

    MODULES_MD.parent.mkdir(parents=True, exist_ok=True)
    MODULES_MD.write_text(render_modules_md(defs), encoding="utf-8")
    AUDIT_SCAFFOLD.write_text(render_audit_scaffold(defs), encoding="utf-8")
    print(f"Wrote {MODULES_MD.relative_to(ROOT)} ({len(defs)} modules)")
    print(f"Wrote {AUDIT_SCAFFOLD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
