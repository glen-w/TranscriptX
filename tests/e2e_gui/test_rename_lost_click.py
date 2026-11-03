"""W1.3: 50 sidebar clicks from Rename Transcript each change the page.

Nightly/Playwright lane (``gui_e2e`` + ``heavy``). Guards fragment autoplay
on Rename stealing subsequent nav clicks.
"""

from __future__ import annotations

import itertools
from urllib.parse import parse_qs, urlparse

import pytest

from tests.e2e_gui.helpers import nav, sidebar, wait
from transcriptx.web.navigation import PAGE_SPECS

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_OPTIONAL_PAGE_KEYS = {"Ask", "Corrections Studio", "Batch Ops"}

_LOOP = [
    spec
    for spec in PAGE_SPECS
    if spec.required_context == "none"
    and spec.subsection != "legacy"
    and spec.key not in _OPTIONAL_PAGE_KEYS
]


def _goto(page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('[data-testid="stApp"]', timeout=120000)
    sidebar(page).get_by_role("button", name="Home").wait_for(timeout=120000)
    wait(page, 1000)


def _url_page(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("page") or []
    return values[0] if values else ""


def test_fifty_nav_clicks_from_rename_each_change_page(seeded_app, page) -> None:
    assert len(_LOOP) >= 8
    _goto(page, seeded_app.base_url)
    nav(page, "Rename Transcript", settle_ms=1500)
    page.wait_for_url(lambda url: "Rename" in _url_page(url), timeout=30000)

    cycle = itertools.cycle(_LOOP)
    previous = _url_page(page.url)
    for _ in range(50):
        spec = next(cycle)
        if spec.key == previous:
            spec = next(cycle)
        nav(page, spec.label, settle_ms=900)
        page.wait_for_url(
            lambda url, key=spec.key: _url_page(url) == key, timeout=30000
        )
        now = _url_page(page.url)
        assert (
            now == spec.key
        ), f"expected page={spec.key!r}, got {now!r} url={page.url}"
        previous = now
