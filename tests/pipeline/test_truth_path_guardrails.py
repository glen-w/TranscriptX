"""Guardrails against truth-path drift in known read-side consumers.

Why allowlist:
- We intentionally scope this check to known consumer zones that should use the
  canonical truth path.
- This is intentionally not repo-wide because write-side code, tests, and
  orchestration/progress paths have different contracts and string vocabularies.
- To add a new consumer safely: add the file to ALLOWLIST_FILES, ensure it
  passes forbidden-pattern checks, and get reviewer sign-off.
"""

from __future__ import annotations

from pathlib import Path
import re

ALLOWLIST_FILES = [
    "src/transcriptx/app/controllers/run_controller.py",
    "src/transcriptx/core/analysis/stats/stats_report.py",
    "src/transcriptx/core/analysis/stats/report_input_resolver.py",
    "src/transcriptx/web/page_modules/overview.py",
    "src/transcriptx/web/services/artifact_service.py",
    "src/transcriptx/app/workflows/analysis.py",
]

FORBIDDEN_PATTERNS = [
    re.compile(r"json\.loads\([^)]*run_results", re.IGNORECASE),
    re.compile(r"\.get\([\"']status[\"']\)\s*==\s*[\"'](success|ok|error)[\"']"),
]


def test_allowlisted_consumers_avoid_local_truth_parsing() -> None:
    repo = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for rel in ALLOWLIST_FILES:
        path = repo / rel
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                violations.append(f"{rel}: {pattern.pattern} -> {match.group(0)!r}")
    assert (
        not violations
    ), "Forbidden local truth parsing patterns found:\n" + "\n".join(violations)
