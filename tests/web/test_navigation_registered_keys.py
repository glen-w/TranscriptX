"""Cross-module session keys live in state.py, not as string literals."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web import navigation, state

_WEB_ROOT = Path(state.__file__).resolve().parent
_CROSS_MODULE_LITERALS = (
    '"run_analysis_target"',
    '"speakers_selected_profile"',
    '"settings_hub_selected_tab"',
)


@pytest.mark.unit
def test_navigation_module_uses_registered_profile_and_target_keys() -> None:
    src = Path(navigation.__file__).read_text(encoding="utf-8")
    assert '"run_analysis_target"' not in src
    assert '"speakers_selected_profile"' not in src
    assert "SPEAKERS_SELECTED_PROFILE_KEY" in src
    assert state.RUN_ANALYSIS_TARGET_KEY == "run_analysis_target"
    assert state.SPEAKERS_SELECTED_PROFILE_KEY == "speakers_selected_profile"


@pytest.mark.unit
def test_web_src_has_no_cross_module_key_literals() -> None:
    """W1.4: grep 0 literal cross-module keys outside state.py."""
    offenders: list[str] = []
    for path in _WEB_ROOT.rglob("*.py"):
        if path.name == "state.py":
            continue
        text = path.read_text(encoding="utf-8")
        for lit in _CROSS_MODULE_LITERALS:
            if lit in text:
                offenders.append(f"{path.relative_to(_WEB_ROOT)}: {lit}")
    assert (
        not offenders
    ), "cross-module keys must use state.py constants:\n" + "\n".join(offenders)
