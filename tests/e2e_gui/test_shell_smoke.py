"""Shell smoke: every sidebar page paints styled, with a complete sidebar.

Guards the two 1.1.0 shell regressions (perf ``section()`` swallowing
``st.rerun()`` → truncated sidebar; once-per-session CSS → unstyled app) and
keeps a cheap budget on page size. Runs against the seeded tiny library so it
stays under a few minutes; intended for the PR gate
(``make test-gui-shell-smoke``).
"""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    main_area,
    nav,
    select_transcript,
    sidebar,
    wait,
)
from transcriptx.web.navigation import PAGE_SPECS

pytestmark = [pytest.mark.gui_e2e, pytest.mark.gui_shell_smoke]

# Pages that are env-gated (hidden from the sidebar unless enabled) or legacy.
_OPTIONAL_PAGE_KEYS = {"Ask", "Corrections Studio", "Batch Ops"}

# Generous ceilings; the point is to catch a page that paints every panel.
DOM_NODE_BUDGET = {"Settings": 12_000, "Diagnostics": 6_000}
DEFAULT_DOM_NODE_BUDGET = 4_500

_STYLE_PROBE = (
    "() => Array.from(document.querySelectorAll('style'))"
    ".filter(s => s.textContent.includes('tx-sidebar-brand')).length"
)
_VISIBLE_LOGOS = (
    "() => Array.from(document.querySelectorAll('.tx-sidebar-brand img'))"
    ".filter(i => i.offsetParent !== null && getComputedStyle(i).display !== 'none').length"
)
_DOM_NODES = "() => document.querySelectorAll('*').length"
_NAV_LABELS = (
    "() => Array.from(document.querySelectorAll('[data-testid=\"stSidebar\"] button'))"
    ".map(b => (b.innerText || '').trim())"
)


def _nav_labels(page) -> list[str]:
    return list(page.evaluate(_NAV_LABELS))


def _goto(page, base_url: str) -> None:
    """Cold start without the shared helper's reload fallback (cold imports can
    exceed 20 s on a fresh server; a reload mid-hydration hangs the test)."""
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('[data-testid="stApp"]', timeout=120000)
    sidebar(page).get_by_role("button", name="Home").wait_for(timeout=120000)
    wait(page, 1000)


def _expected_pages() -> list[tuple[str, str]]:
    return [
        (spec.key, spec.label) for spec in PAGE_SPECS if spec.subsection != "legacy"
    ]


def test_shell_every_page_paints_styled_with_full_sidebar(seeded_run_app, page) -> None:
    console_errors: list[str] = []
    page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
    page.on(
        "console",
        lambda msg: (
            console_errors.append(msg.text)
            if msg.type == "error" and "favicon" not in msg.text
            else None
        ),
    )

    _goto(page, seeded_run_app.base_url)
    initial_labels = _nav_labels(page)
    assert "Home" in initial_labels and "Settings" in initial_labels
    assert page.evaluate(_STYLE_PROBE) == 1, "global CSS missing on first paint"

    # Bind transcript + run so run-scoped VIEW pages are enabled.
    select_transcript(page)

    visited: list[str] = []
    for key, label in _expected_pages():
        sb_btn = sidebar(page).get_by_role("button", name=label, exact=True)
        if sb_btn.count() == 0:
            assert key in _OPTIONAL_PAGE_KEYS, f"nav entry missing: {label!r}"
            continue
        if sb_btn.last.is_disabled():
            pytest.fail(f"nav entry {label!r} disabled with transcript+run bound")

        nav(page, label, settle_ms=1500)
        visited.append(key)

        labels_now = _nav_labels(page)
        assert (
            len(labels_now) >= len(initial_labels) - 1
        ), f"sidebar truncated after {label!r}: {labels_now}"
        assert (
            "Settings" in labels_now and "Diagnostics" in labels_now
        ), f"sidebar lost tail after {label!r}: {labels_now}"
        assert page.evaluate(_STYLE_PROBE) == 1, f"global CSS lost after {label!r}"
        assert page.evaluate(_VISIBLE_LOGOS) == 1, f"logo swap broken after {label!r}"
        assert (
            page.locator('[data-testid="stException"]').count() == 0
        ), f"exception rendered on {label!r}"
        body = (main_area(page).inner_text() or "").strip()
        assert body, f"empty main area on {label!r}"

        nodes = page.evaluate(_DOM_NODES)
        budget = DOM_NODE_BUDGET.get(key, DEFAULT_DOM_NODE_BUDGET)
        assert nodes <= budget, f"{label!r} painted {nodes} DOM nodes (> {budget})"

    assert len(visited) >= 18, f"too few pages reachable: {visited}"
    assert not console_errors, f"browser console errors: {console_errors[:5]}"


def test_shell_url_deep_link_and_reload_keep_view_context(seeded_run_app, page) -> None:
    """URL carries page + subject + run: deep links open the view and a refresh
    does not land on Home."""
    ws = seeded_run_app.workspace
    assert ws.slug and ws.run_id
    deep = (
        f"{seeded_run_app.base_url}/?page=Overview&subject_type=transcript"
        f"&subject_id={ws.slug}&run_id={ws.run_id}"
    )
    _goto(page, deep)
    wait(page, 2500)
    before = (main_area(page).inner_text() or "")[:300]
    assert (
        "Overview" in before or "Summary" in before
    ), f"deep link did not open Overview: {before!r}"
    assert "page=Overview" in page.url and f"run_id={ws.run_id}" in page.url, page.url

    # Navigate to Charts via the sidebar, then refresh: URL must follow and
    # the reload must restore Charts (not Home).
    nav(page, "Charts", settle_ms=1500)
    # Query params are pushed with the run's forward messages; a cold Charts
    # paint (first Plotly import) can take a while on CI.
    page.wait_for_url(lambda url: "page=Charts" in url, timeout=60000)
    page.reload(wait_until="domcontentloaded", timeout=60000)
    sidebar(page).get_by_role("button", name="Home").wait_for(timeout=120000)
    wait(page, 3000)
    after = (main_area(page).inner_text() or "")[:300]
    assert (
        "Charts" in after or "chart" in after.lower()
    ), f"reload lost context; main now starts with: {after!r}"
    assert "page=Charts" in page.url
