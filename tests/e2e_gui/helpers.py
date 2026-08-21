"""Streamlit Playwright helpers for GUI E2E and docs media capture."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.sync_api import Page, expect
except ImportError:  # pragma: no cover - optional for Core+dev / CI collection
    Page = Any  # type: ignore[misc,assignment]
    expect = None  # type: ignore[assignment]


DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
DEFAULT_SETTLE_MS = 2500


def wait(page: Page, ms: int = DEFAULT_SETTLE_MS) -> None:
    """Wait for Streamlit reruns / network settle."""
    page.wait_for_timeout(ms)


def wait_for_streamlit(page: Page, *, timeout_ms: int = 60000) -> None:
    """Wait until the Streamlit app shell is present."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
    # Give the first script run time to paint the sidebar.
    wait(page, 2000)


def sidebar(page: Page):
    return page.locator('[data-testid="stSidebar"]')


def main_area(page: Page):
    return page.locator('[data-testid="stMain"], section.main').first


def nav(page: Page, label: str, *, settle_ms: int = 3500) -> None:
    """Click a sidebar navigation button by exact label.

    Prefer the last matching sidebar button so subject-type controls named
    ``Transcript`` / ``Group`` (segmented control) do not steal the click from
    the VIEW page nav entries.
    """
    sb = sidebar(page)
    btn = sb.get_by_role("button", name=label, exact=True)
    expect(btn.last).to_be_visible(timeout=20000)
    btn.last.click(force=True, timeout=20000)
    wait(page, settle_ms)


def goto_app(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    wait_for_streamlit(page)


def select_transcript(page: Page, needle: str = "planning_review") -> None:
    """Select a transcript by clicking its Library title button."""
    nav(page, "Library")
    search = page.get_by_label("Search transcripts")
    if search.count():
        search.first.fill(needle)
        wait(page, 800)
    main = main_area(page)
    title_btn = main.get_by_role("button", name=needle, exact=False)
    if title_btn.count() == 0:
        title_btn = main.get_by_role("button", name="planning", exact=False)
    expect(title_btn.first).to_be_visible(timeout=20000)
    title_btn.first.click(force=True)
    wait(page, 2500)

    sb_boxes = sidebar(page).locator('[data-testid="stSelectbox"]')
    if sb_boxes.count():
        sb_boxes.first.click()
        wait(page, 600)
        opt2 = page.locator('[role="option"]').filter(has_text=needle)
        if opt2.count() == 0:
            opt2 = page.locator('[role="option"]').filter(has_text="planning")
        if opt2.count():
            opt2.first.click()
            wait(page, 2000)


def library_option_labels(page: Page) -> list[str]:
    """Return visible Library list titles and caption lines."""
    nav(page, "Library")
    main = main_area(page)
    # Title buttons are the clickable list rows; include captions for workflow marks.
    expect(main.get_by_role("button").first).to_be_visible(timeout=20000)
    return [line for line in main.inner_text().splitlines() if line.strip()]


def assert_library_lists_transcript(page: Page, needle: str = "planning") -> None:
    opts = library_option_labels(page)
    joined = "\n".join(opts)
    assert any(
        needle.lower() in o.lower() for o in opts
    ), f"Expected Library option containing {needle!r}; options={opts!r}"
    assert "No transcripts found" not in page_text(page)


def open_speaker_identification(page: Page, needle: str = "planning") -> None:
    """Open Speaker Identification with a transcript selected.

    Prefer the Library post-select action (passes subject context). Fall back to
    the page's own transcript picker when needed.
    """
    select_transcript(page, needle=needle)
    run_sid = page.get_by_role("button", name="Run Speaker ID")
    if run_sid.count():
        run_sid.first.click(force=True)
        wait(page, 3500)
    else:
        nav(page, "Speaker Identification")
        wait(page, 2500)

    body = page_text(page)
    if "SPEAKER_" not in body and "Assign name" not in body:
        # Select transcript on the Speaker Identification page itself.
        boxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
        if boxes.count() == 0:
            boxes = page.locator('[data-testid="stSelectbox"]')
        if boxes.count():
            boxes.first.click()
            wait(page, 600)
            opt = page.locator('[role="option"]').filter(has_text=needle)
            if opt.count() == 0:
                opt = page.locator('[role="option"]').filter(has_text="planning")
            if opt.count():
                opt.first.click()
                wait(page, 3500)


def upload_transcript(page: Page, path: Path) -> None:
    """Upload a transcript file on Import Transcript and submit the form."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    nav(page, "Import Transcript")
    expect(page.get_by_text("Import Transcript").first).to_be_visible(timeout=20000)

    file_inputs = page.locator('input[type="file"]')
    expect(file_inputs.first).to_be_attached(timeout=20000)
    # First uploader is the transcript chooser (section 1).
    file_inputs.first.set_input_files(str(path))
    wait(page, 1500)

    candidates = page.locator(
        '[data-testid="stMain"] button, section.main button'
    ).filter(has_text="Import Transcript")
    if candidates.count():
        candidates.first.click(force=True)
    else:
        page.get_by_role("button", name="Import Transcript", exact=True).last.click(
            force=True
        )
    wait(page, 4000)


def assert_text_visible(page: Page, text: str, *, timeout_ms: int = 20000) -> None:
    expect(page.get_by_text(text, exact=False).first).to_be_visible(timeout=timeout_ms)


def click_main_button(page: Page, name: str, *, exact: bool = True) -> None:
    """Click a button in the main pane by accessible name."""
    root = page.locator('[data-testid="stMain"], section.main').first
    btn = root.get_by_role("button", name=name, exact=exact)
    expect(btn.first).to_be_visible(timeout=20000)
    btn.first.click(force=True)
    wait(page, 2500)


def select_analysis_preset(page: Page, label: str) -> None:
    """Select Quick / Balanced / Thorough / Custom via segmented control or buttons."""
    root = page.locator('[data-testid="stMain"], section.main').first
    control = root.get_by_role("button", name=label, exact=True)
    if control.count() == 0:
        control = root.get_by_text(label, exact=True)
    expect(control.first).to_be_visible(timeout=20000)
    control.first.click(force=True)
    wait(page, 2000)


def launch_analysis(page: Page) -> None:
    click_main_button(page, "Run analysis", exact=True)


def wait_for_analysis_finish(page: Page, *, timeout_ms: int = 300000) -> None:
    """Wait until analysis progress reports completion or a success banner appears."""
    deadline_phrases = (
        "Completed",
        "complete",
        "Partial success",
        "partial",
        "Analysis finished",
        "output folder",
        "Outputs:",
        "Run summary",
        "successfully",
        "Processed",
    )
    main = page.locator('[data-testid="stMain"], section.main').first
    elapsed = 0
    step = 2000
    text = ""
    while elapsed < timeout_ms:
        try:
            text = main.inner_text(timeout=5000)
        except Exception:
            pass
        lower = text.lower()
        if any(p.lower() in lower for p in deadline_phrases):
            if (
                "completed" in lower
                or "partial" in lower
                or "success" in lower
                or "output" in lower
            ):
                wait(page, 1500)
                return
        wait(page, step)
        elapsed += step
    raise TimeoutError(
        f"Analysis did not finish within {timeout_ms}ms; last text head: {text[:500]!r}"
    )


def fill_assign_name(page: Page, name: str) -> None:
    """Fill Speaker Identification 'Assign name' and save."""
    root = page.locator('[data-testid="stMain"], section.main').first
    # Prefer the text input; get_by_label can match the help tooltip button.
    inp = root.locator('[data-testid="stTextInput"] input')
    if inp.count() == 0:
        inp = root.get_by_placeholder("Type speaker name…")
    if inp.count() == 0:
        inp = root.locator('input[aria-label="Assign name"]')
    expect(inp.first).to_be_visible(timeout=20000)
    inp.first.click()
    inp.first.fill(name)
    wait(page, 500)
    save = root.get_by_role("button", name="Save name", exact=True)
    expect(save.first).to_be_visible(timeout=10000)
    save.first.click(force=True)
    wait(page, 3000)


def click_section_tab(page: Page, label: str) -> None:
    """Click Insights/Artifacts section tabs (Summary, Highlights, …)."""
    root = page.locator('[data-testid="stMain"], section.main').first
    tab = root.get_by_role("button", name=label, exact=True)
    if tab.count() == 0:
        tab = root.get_by_text(label, exact=True)
    if tab.count():
        tab.first.click(force=True)
        wait(page, 2000)


def jump_to_transcript_if_present(page: Page) -> bool:
    """Click 'Jump to transcript' when available. Returns True if clicked."""
    jump = page.get_by_text("Jump to transcript", exact=False)
    if jump.count() == 0:
        return False
    try:
        jump.first.click(force=True)
        wait(page, 2500)
        return True
    except Exception:
        return False


def page_text(page: Page) -> str:
    try:
        return page.locator('[data-testid="stMain"], section.main').first.inner_text(
            timeout=10000
        )
    except Exception:
        return page.inner_text("body")


def fixture_planning_review() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "workflows"
        / "fixtures"
        / "planning_review.json"
    )


def optional_screenshot(page: Page, path: Optional[Path]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)


def expand_labeled(page: Page, label: str) -> None:
    """Open a Streamlit expander / disclosure whose summary contains ``label``."""
    root = page.locator('[data-testid="stMain"], section.main').first
    # Streamlit expanders expose a summary button / details summary.
    candidates = root.locator("details summary, [data-testid='stExpander'] summary")
    count = candidates.count()
    for i in range(count):
        node = candidates.nth(i)
        try:
            if label.lower() in (node.inner_text() or "").lower():
                node.click(force=True)
                wait(page, 1000)
                return
        except Exception:
            continue
    # Fallback: click any text match in main.
    text = root.get_by_text(label, exact=False)
    if text.count():
        text.first.click(force=True)
        wait(page, 1000)


def set_checkbox_labeled(page: Page, label: str, *, checked: bool = True) -> None:
    """Toggle a Streamlit checkbox by accessible label."""
    root = page.locator('[data-testid="stMain"], section.main').first

    def _resolve():
        # Streamlit 1.6x React Aria checkboxes: visually-hidden native <input>.
        by_aria = root.locator(f'input[type="checkbox"][aria-label="{label}"]')
        if by_aria.count():
            return by_aria.first
        role = root.get_by_role("checkbox", name=label, exact=True)
        if role.count():
            return role.first
        blocks = root.locator('[data-testid="stCheckbox"]').filter(has_text=label)
        if blocks.count():
            native = blocks.first.locator('input[type="checkbox"]')
            if native.count():
                return native.first
            return blocks.first
        raise RuntimeError(f"checkbox not found for label {label!r}")

    box = _resolve()
    expect(box).to_be_attached(timeout=20000)
    if box.is_checked() != checked:
        # React Aria hidden inputs ignore Playwright click/check; focus+Space works.
        box.focus()
        page.keyboard.press("Space")
        wait(page, 2500)
        box = _resolve()
        if box.is_checked() != checked:
            box.focus()
            page.keyboard.press("Space")
            wait(page, 2500)
            box = _resolve()
    if box.is_checked() != checked:
        raise RuntimeError(
            f"checkbox {label!r} did not become checked={checked} "
            f"(after={box.is_checked()!r})"
        )


def fill_main_text_input(page: Page, label: str, value: str) -> None:
    """Fill a main-pane text input by label or nearby caption."""
    root = page.locator('[data-testid="stMain"], section.main').first
    # Prefer stTextInput blocks: get_by_label often matches Streamlit help buttons
    # (aria-label "Help for …") which are not fillable.
    blocks = root.locator('[data-testid="stTextInput"]')
    for i in range(blocks.count()):
        block = blocks.nth(i)
        if label.lower() in (block.inner_text() or "").lower():
            inp = block.locator("input:not([disabled])")
            if inp.count() == 0:
                inp = block.locator("input")
            expect(inp.first).to_be_visible(timeout=10000)
            inp.first.click()
            inp.first.fill(value)
            wait(page, 500)
            return

    # Fallback: get_by_label but only real editable fields.
    by_label = root.get_by_label(label, exact=False)
    for i in range(by_label.count()):
        el = by_label.nth(i)
        try:
            tag = (el.evaluate("e => e.tagName") or "").upper()
        except Exception:
            continue
        if tag not in ("INPUT", "TEXTAREA"):
            continue
        el.click()
        el.fill(value)
        wait(page, 500)
        return
    raise RuntimeError(f"text input not found for label {label!r}")


def create_group_via_ui(
    page: Page, *, name: str, transcript_needle: str = "planning"
) -> None:
    """Create a group from the Groups page expander."""
    nav(page, "Groups")
    wait(page, 2500)
    expand_labeled(page, "Create new group")
    fill_main_text_input(page, "Name", name)

    # Multiselect: open and pick a matching option.
    multi = page.locator('[data-testid="stMultiSelect"]')
    expect(multi.first).to_be_visible(timeout=20000)
    multi.first.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=transcript_needle)
    if opt.count() == 0:
        opt = page.locator('[role="option"]').filter(has_text="planning")
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
    wait(page, 800)
    page.keyboard.press("Escape")
    wait(page, 400)

    click_main_button(page, "Create group", exact=True)
    wait(page, 3500)


def open_correct_mode_and_propose(
    page: Page,
    *,
    find_text: str,
    replacement: str,
) -> None:
    """Enable Correct mode on Transcript and propose a manual correction."""
    # Planning-review speakers are still SPEAKER_* placeholders; Correct-mode
    # propose panels only render for *visible* segments.
    set_checkbox_labeled(page, "Show unnamed speakers", checked=True)
    set_checkbox_labeled(page, "Correct mode", checked=True)
    wait(page, 2500)
    root = page.locator('[data-testid="stMain"], section.main').first
    # Wait until at least one propose expander is present (Streamlit rerun).
    deadline = time.time() + 20
    while time.time() < deadline:
        n = (
            root.locator("details summary, [data-testid='stExpander'] summary")
            .filter(has_text="Propose correction")
            .count()
        )
        if n:
            break
        wait(page, 500)
    expand_labeled(page, "Propose correction")
    fill_main_text_input(page, "Find exact text in segment", find_text)
    fill_main_text_input(page, "Replacement", replacement)
    click_main_button(page, "Propose", exact=True)
    wait(page, 3000)


def rename_transcript_via_ui(
    page: Page, *, new_name: str, needle: str = "planning"
) -> None:
    """Rename the selected transcript on the Rename Transcript page."""
    nav(page, "Rename Transcript")
    wait(page, 2500)
    boxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
    if boxes.count() == 0:
        boxes = page.locator('[data-testid="stSelectbox"]')
    expect(boxes.first).to_be_visible(timeout=20000)
    boxes.first.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=needle)
    if opt.count() == 0:
        opt = page.locator('[role="option"]').filter(has_text="planning")
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
    wait(page, 2500)

    fill_main_text_input(page, "New file name", new_name)
    # Form submit button.
    root = page.locator('[data-testid="stMain"], section.main').first
    btn = root.get_by_role("button", name="Rename", exact=True)
    expect(btn.first).to_be_visible(timeout=15000)
    btn.first.click(force=True)
    wait(page, 4000)
