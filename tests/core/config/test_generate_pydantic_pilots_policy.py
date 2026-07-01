"""Policy tests for generate_pydantic_pilots.py (scaffold-only bridge output)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "generate_pydantic_pilots.py"
BRIDGE = REPO_ROOT / "src" / "transcriptx" / "core" / "config" / "pydantic_bridge.py"
HELPERS = (
    REPO_ROOT / "src" / "transcriptx" / "core" / "config" / "pydantic_bridge_helpers.py"
)


def test_generator_help_documents_scaffold_write_bridge() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert "--write-bridge" in result.stdout
    assert "scaffold" in result.stdout.lower()


def test_generator_source_does_not_inline_bridge_behavior() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def write_bridge_scaffold" in source
    assert "def _extract_subtree_overrides" not in source
    assert "field_name in spec.model.model_fields" not in source
    assert "dotpath_belongs_to_model" not in source


def test_write_bridge_scaffold_has_no_behavioral_logic() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write-bridge"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    out = result.stdout
    assert "PydanticPilotSpec(" in out
    assert "pydantic_bridge_helpers" in out
    assert "def _extract_subtree_overrides" not in out
    assert "def dotpath_belongs_to_model" not in out


def test_helpers_module_has_nested_override_extraction() -> None:
    source = HELPERS.read_text(encoding="utf-8")
    assert "dotpath_belongs_to_model" in source
    assert "cursor[parts[-1]] = value" in source


def test_bridge_imports_shared_helpers() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    assert "pydantic_bridge_helpers" in source
    assert "def _extract_subtree_overrides" not in source
