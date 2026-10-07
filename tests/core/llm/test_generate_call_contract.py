"""Contract: every ``LLMClient.generate`` / ``generate_json`` call site is keyword-safe.

Catches the rename-suggest regression where a positional prompt + ``system=``
was swallowed as empty cues. Scans production sources under ``src/transcriptx``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "transcriptx"

_ALLOWED_KWONLY = frozenset(
    {
        "prompt",
        "system_prompt",
        "temperature",
        "max_tokens",
        "response_format",
    }
)


def _is_generate_attr(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "generate"


def _is_generate_json_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "generate_json":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "generate_json"


def _call_issues(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_generate_attr(node.func):
            # Skip non-LLM chart ``.generate(ctx, outcome)`` style calls: those
            # pass positional args and never use LLMClient kwargs.
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            if not kw_names.intersection(_ALLOWED_KWONLY) and node.args:
                continue
            if node.args:
                issues.append(
                    f"{path}:{node.lineno}: generate() must use keyword-only "
                    f"args (got {len(node.args)} positional)"
                )
            bad = [
                kw.arg
                for kw in node.keywords
                if kw.arg is not None and kw.arg not in _ALLOWED_KWONLY
            ]
            if bad:
                issues.append(
                    f"{path}:{node.lineno}: generate() unknown kwargs {bad}; "
                    f"expected subset of {sorted(_ALLOWED_KWONLY)}"
                )
            if "prompt" not in kw_names and not node.args:
                issues.append(f"{path}:{node.lineno}: generate() missing prompt=")
            if "system" in {kw.arg for kw in node.keywords}:
                issues.append(
                    f"{path}:{node.lineno}: use system_prompt= not system="
                )
        elif _is_generate_json_name(node.func):
            if node.args and not (
                len(node.args) == 1 and not any(kw.arg == "client" for kw in node.keywords)
            ):
                # Allow generate_json(client, prompt=..., ...) — client positional only.
                if len(node.args) > 1:
                    issues.append(
                        f"{path}:{node.lineno}: generate_json() only client may "
                        "be positional; use keyword prompt=/system_prompt="
                    )
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            if "system" in kw_names:
                issues.append(
                    f"{path}:{node.lineno}: use system_prompt= not system="
                )
            if "prompt" not in kw_names:
                issues.append(
                    f"{path}:{node.lineno}: generate_json() missing prompt="
                )
    return issues


def _production_py_files() -> list[Path]:
    return sorted(
        p
        for p in SRC_ROOT.rglob("*.py")
        if p.is_file() and "migrations" not in p.parts
    )


@pytest.mark.unit
def test_llm_generate_call_sites_are_keyword_safe() -> None:
    all_issues: list[str] = []
    for path in _production_py_files():
        all_issues.extend(_call_issues(path))
    assert not all_issues, "\n".join(all_issues)


@pytest.mark.unit
def test_json_format_consumers_have_generate_sites() -> None:
    """Each JSON consumer id should appear near a generate / generate_json call.

    Soft presence check: rename + speaker suggestions must call generate_json.
    """
    rename = (
        SRC_ROOT / "core" / "utils" / "rename" / "suggestions" / "llm.py"
    ).read_text(encoding="utf-8")
    speaker = (
        SRC_ROOT
        / "core"
        / "speaker_profiles"
        / "identify"
        / "suggestions"
        / "llm_assign.py"
    ).read_text(encoding="utf-8")
    assert "generate_json(" in rename
    assert "prompt=" in rename
    assert "system_prompt=" in rename
    assert "RENAME_LLM_JSON_SCHEMA" in rename
    assert "generate_json(" in speaker
    assert "system_prompt=" in speaker
