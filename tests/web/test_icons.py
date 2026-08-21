"""Contracts for the shared Material icon registry."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from transcriptx.web import icons as ic
from transcriptx.web.action_menus.catalog import ACTIONS, icon_for
from transcriptx.web.action_menus.ids import ActionId

_TOKEN = re.compile(r"^:material/[a-z0-9_]+:$")

_WEB_ROOT = Path(ic.__file__).parent
_BUTTON_CALLS = {"button", "form_submit_button", "download_button"}


def _constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(ic).items()
        if not name.startswith("_") and isinstance(value, str)
    }


def test_every_constant_is_a_material_token() -> None:
    constants = _constants()
    assert constants, "registry should not be empty"
    for name, value in constants.items():
        assert _TOKEN.match(value), f"{name}={value!r} is not a :material/<glyph>: token"


def test_constant_names_are_upper_snake_case() -> None:
    for name in _constants():
        assert name.isupper(), f"{name} should be UPPER_SNAKE_CASE"


def test_action_catalog_icons_come_from_the_registry() -> None:
    known = set(_constants().values())
    for action in ACTIONS:
        assert action.icon in known, f"{action.id} uses an unregistered icon"


def test_icon_for_resolves_every_action() -> None:
    for action in ActionId:
        assert _TOKEN.match(icon_for(action))


def test_no_inline_material_tokens_outside_the_registry() -> None:
    offenders = []
    for path in sorted(_WEB_ROOT.rglob("*.py")):
        if path.name == "icons.py":
            continue
        if ":material/" in path.read_text():
            offenders.append(str(path.relative_to(_WEB_ROOT)))
    assert not offenders, f"inline Material tokens found; use icons.py instead: {offenders}"


def test_buttons_with_literal_labels_declare_an_icon() -> None:
    offenders = []
    for path in sorted(_WEB_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in _BUTTON_CALLS:
                continue
            if any(kw.arg == "icon" for kw in node.keywords):
                continue
            # Dynamic labels (nav rows, module pickers) stay text-only by design.
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            label = node.args[0].value
            offenders.append(f"{path.relative_to(_WEB_ROOT)}:{node.lineno} {label!r}")
    assert not offenders, "buttons with fixed labels must pass icon=: " + "; ".join(offenders)
