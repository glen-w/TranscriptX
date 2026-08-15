"""Streamlit Playwright helpers for GUI E2E and docs media capture."""

from __future__ import annotations

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
    """Select a transcript via Library page dropdown (and sidebar picker if present)."""
    nav(page, "Library")
    boxes = page.locator('[data-testid="stSelectbox"]')
    expect(boxes.first).to_be_visible(timeout=20000)
    target = None
    count = boxes.count()
    for i in range(count):
        txt = boxes.nth(i).inner_text()
        if (
            "Select transcript" in txt
            or "Select a transcript" in txt
            or "Selected Transcript" in txt
            or "transcript" in txt.lower()
        ):
            target = boxes.nth(i)
            break
    if target is None and count:
        target = boxes.first
    if target is None:
        raise RuntimeError("no transcript selectbox found on Library")
    target.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=needle)
    if opt.count() == 0:
        opt = page.locator('[role="option"]').filter(has_text="planning")
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
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
    """Open the Library transcript selectbox and return option labels."""
    nav(page, "Library")
    boxes = page.locator('[data-testid="stSelectbox"]')
    expect(boxes.first).to_be_visible(timeout=20000)
    boxes.first.click()
    wait(page, 800)
    opts = page.locator('[role="option"]').all_text_contents()
    page.keyboard.press("Escape")
    wait(page, 400)
    return opts


def assert_library_lists_transcript(page: Page, needle: str = "planning") -> None:
    opts = library_option_labels(page)
    joined = "\n".join(opts)
    assert any(needle.lower() in o.lower() for o in opts), (
        f"Expected Library option containing {needle!r}; options={opts!r}"
    )
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
