"""Contract: chart helpers that only persist via OutputService must receive it.

Several chart helpers historically accepted ``output_service=None`` and silently
plotted then discarded figures. This AST contract fails when production call
sites invoke those helpers without passing ``output_service``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "transcriptx"


@dataclass(frozen=True)
class _ChartHelperRule:
    """A chart helper that requires ``output_service`` to persist artifacts."""

    name: str
    # Minimum positional arity that includes output_service (1-based count of args).
    # If a call has fewer positionals, ``output_service`` must appear as a keyword.
    min_positional_including_service: int


# Helpers that gate ``save_chart`` on a truthy ``output_service`` (or require it).
_CHART_HELPERS: tuple[_ChartHelperRule, ...] = (
    _ChartHelperRule("plot_understandability_charts", 4),
    _ChartHelperRule("create_loop_network", 4),
    _ChartHelperRule("create_loop_timeline", 5),
    _ChartHelperRule("create_loop_act_analysis", 4),
    _ChartHelperRule("create_combined_timeline", 3),
    _ChartHelperRule("create_speaker_timeline_charts", 3),
    _ChartHelperRule("create_diagnostic_plots", 5),
    _ChartHelperRule("create_discourse_analysis_charts", 4),
    _ChartHelperRule("create_enhanced_global_heatmaps", 6),
    _ChartHelperRule("create_speaker_charts", 7),
    _ChartHelperRule("create_topic_evolution_timeline", 5),
    _ChartHelperRule("create_speaker_topic_engagement_heatmap", 5),
    _ChartHelperRule("create_expected_topic_proportions_bar", 5),
)

_HELPER_BY_NAME = {rule.name: rule for rule in _CHART_HELPERS}

# Call sites that intentionally omit output_service (e.g. unit tests of early-return).
# Production code under src/ should not be allowlisted.
_ALLOWLISTED_PATHS: frozenset[Path] = frozenset()


def _call_func_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _passes_output_service(node: ast.Call, rule: _ChartHelperRule) -> bool:
    for kw in node.keywords:
        if kw.arg == "output_service":
            # Explicit None is still a wiring bug for persistence helpers.
            if isinstance(kw.value, ast.Constant) and kw.value.value is None:
                return False
            return True
    return len(node.args) >= rule.min_positional_including_service


def _scan_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_func_name(node)
        if name is None or name not in _HELPER_BY_NAME:
            continue
        rule = _HELPER_BY_NAME[name]
        if not _passes_output_service(node, rule):
            rel = path.relative_to(REPO_ROOT).as_posix()
            violations.append(
                f"{rel}:{node.lineno}: {name}(...) missing output_service"
            )
    return violations


@pytest.mark.unit
def test_chart_helpers_receive_output_service_in_production_code() -> None:
    """Fail if known gated chart helpers are called without output_service."""
    violations: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path in _ALLOWLISTED_PATHS:
            continue
        violations.extend(_scan_file(path))

    assert violations == [], (
        "Chart helpers called without output_service "
        "(charts will not be persisted):\n" + "\n".join(violations)
    )


@pytest.mark.unit
def test_chart_helper_registry_covers_known_silent_noop_apis() -> None:
    """Keep the registry honest: listed helpers must exist in source."""
    found: set[str] = set()
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in _HELPER_BY_NAME:
                    found.add(node.name)
    missing = sorted(set(_HELPER_BY_NAME) - found)
    assert missing == [], f"Registry names not found as defs: {missing}"
