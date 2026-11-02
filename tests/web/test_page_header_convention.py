"""One header system: page modules use ``render_page_shell`` / run-scoped shell.

Three header styles (``render_page_shell``, a raw ``main-header`` div, and
``st.title``) painted three different visual weights and two of them lost
their styling with the 2026-10 CSS regression. Keep new pages on the shell.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGE_MODULES = Path(__file__).resolve().parents[2] / "src/transcriptx/web/page_modules"

_FORBIDDEN = (
    re.compile(r'class="main-header"'),
    re.compile(r"\bst\.title\("),
    re.compile(r"\bst\.set_page_config\("),  # only the app shell configures the page
)


@pytest.mark.unit
def test_page_modules_use_the_shared_page_shell() -> None:
    offenders: list[str] = []
    for path in sorted(PAGE_MODULES.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for pat in _FORBIDDEN:
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.name}:{line}: {m.group(0)}")
    assert not offenders, "page modules must use render_page_shell:\n" + "\n".join(
        offenders
    )
