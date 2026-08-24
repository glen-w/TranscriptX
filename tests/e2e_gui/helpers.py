"""Streamlit Playwright helpers for GUI E2E and docs media capture."""

from __future__ import annotations

import re
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


def wait_for_streamlit(page: Page, *, timeout_ms: int = 90000) -> None:
    """Wait until the Streamlit app shell and sidebar nav have hydrated."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
    # Sidebar widgets start as stSkeleton (~3s) and become real buttons (~8s).
    home = sidebar(page).get_by_role("button", name="Home")
    first_wait = min(20000, timeout_ms)
    try:
        expect(home).to_be_visible(timeout=first_wait)
    except Exception:
        # Later tests in a suite can land on a shell that never hydrates;
        # one reload is cheaper than a 90s miss.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
        expect(sidebar(page).get_by_role("button", name="Home")).to_be_visible(
            timeout=timeout_ms
        )
    wait(page, 500)


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
    if btn.count() == 0 and label == "Speaker Identification":
        btn = sb.get_by_role("button", name="Speaker ID", exact=True)
    expect(btn.last).to_be_visible(timeout=30000)
    btn.last.click(force=True, timeout=20000)
    wait(page, settle_ms)


def goto_app(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    wait_for_streamlit(page)


def _library_search_input(page: Page):
    """Resolve the Library search field without matching help-tooltip buttons."""
    root = page.locator('[data-testid="stMain"], section.main').first
    blocks = root.locator('[data-testid="stTextInput"]')
    for i in range(blocks.count()):
        block = blocks.nth(i)
        if "search transcripts" in (block.inner_text() or "").lower():
            inp = block.locator("input")
            if inp.count():
                return inp.first
    return root.get_by_placeholder("Title or filename")


def library_table_rows(page: Page) -> list[str]:
    """Return visible Library inventory row text (excludes header row)."""
    nav(page, "Library")
    grid = page.locator('[data-testid="stDataFrame"]')
    expect(grid.first).to_be_visible(timeout=20000)
    rows = grid.locator('[role="row"]')
    out: list[str] = []
    for i in range(rows.count()):
        text = (rows.nth(i).inner_text() or "").strip()
        if not text or text.startswith("Transcript"):
            continue
        out.append(text)
    if out:
        return out
    # Fallback when dataframe cells do not expose row text (older Playwright builds).
    return [line for line in grid.inner_text().splitlines() if line.strip()]


def library_option_labels(page: Page) -> list[str]:
    """Return visible Library table text lines (titles and workflow columns)."""
    return library_table_rows(page)


def assert_library_lists_transcript(page: Page, needle: str = "planning") -> None:
    opts = library_option_labels(page)
    joined = "\n".join(opts)
    body = page_text(page)
    assert any(
        needle.lower() in o.lower() for o in opts
    ) or needle.lower() in body.lower() or f"of 1 transcript" in body.lower(), (
        f"Expected Library option containing {needle!r}; options={opts!r}; "
        f"body_head={body[:500]!r}"
    )
    assert "No transcripts found" not in body


def select_transcript(page: Page, needle: str = "planning_review") -> None:
    """Select a transcript via the sidebar workspace picker.

    Library dataframe cells are often non-interactive in headless Playwright
    (glide-data-grid virtualisation), so VIEW pages use the sidebar pickers
    after navigating to Overview. When pickers are not yet hydrated (fresh
    import), fall back to confirming the transcript appears in Library.
    """
    nav(page, "Overview")
    wait(page, 2500)
    sb = sidebar(page)
    boxes = sb.locator('[data-testid="stSelectbox"]')
    if boxes.count() == 0:
        nav(page, "Library")
        wait(page, 2500)
        body = page_text(page)
        if not (
            needle.lower() in body.lower()
            or "planning" in body.lower()
            or "of 1 transcript" in body.lower()
        ):
            raise AssertionError(
                f"Transcript picker unavailable and Library missing {needle!r}; "
                f"body_head={body[:500]!r}"
            )
        return

    boxes.first.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=needle)
    if opt.count() == 0:
        opt = page.locator('[role="option"]').filter(has_text="planning")
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
    wait(page, 2500)

    # Bind a run when the run picker lists options (seeded_run_app journeys).
    boxes = sb.locator('[data-testid="stSelectbox"]')
    if boxes.count() >= 2:
        try:
            boxes.nth(1).click()
            wait(page, 800)
            run_opts = page.locator('[role="option"]')
            if run_opts.count():
                # Prefer a concrete run id over placeholder labels.
                chosen = None
                for i in range(run_opts.count()):
                    label = run_opts.nth(i).inner_text() or ""
                    if label and "select" not in label.lower():
                        chosen = run_opts.nth(i)
                        break
                (chosen or run_opts.first).click()
                wait(page, 2500)
        except Exception:
            pass


def _pick_transcript_on_speaker_id_page(page: Page, needle: str) -> None:
    """Select a transcript from the Speaker Identification page picker."""
    boxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
    if boxes.count() == 0:
        boxes = page.locator('[data-testid="stSelectbox"]')
    expect(boxes.first).to_be_visible(timeout=20000)
    boxes.first.click()
    wait(page, 600)
    opt = page.locator('[role="option"]').filter(has_text=needle)
    if opt.count() == 0:
        opt = page.locator('[role="option"]').filter(has_text="planning")
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
    wait(page, 3500)


def _speaker_id_workspace_ready(page: Page) -> bool:
    """True when CCv2 workspace or classic Speaker ID content is painted."""
    if speaker_id_workspace(page).count():
        return True
    body = page_text(page)
    return "SPEAKER_" in body or "Assign name" in body or "Name" in body


def open_speaker_identification(page: Page, needle: str = "planning") -> None:
    """Open Speaker Identification with a transcript selected.

    Prefer the page's own transcript picker (reliable with canvas Library grids).
    Fall back to Library selection + Run Speaker ID when the picker is absent.
    Targets the CCv2 workspace when ``transcriptx-workspaces`` is installed.
    """
    nav(page, "Speaker Identification")
    wait(page, 2500)
    if not _speaker_id_workspace_ready(page):
        try:
            _pick_transcript_on_speaker_id_page(page, needle)
        except Exception:
            select_transcript(page, needle=needle)
            run_sid = page.get_by_role("button", name="Run Speaker ID")
            if run_sid.count():
                run_sid.first.click(force=True)
                wait(page, 3500)
            else:
                nav(page, "Speaker Identification")
                wait(page, 2500)
                _pick_transcript_on_speaker_id_page(page, needle)

    if not _speaker_id_workspace_ready(page):
        _pick_transcript_on_speaker_id_page(page, needle)

    # CCv2 mounts after the picker selection; wait for the workspace host
    # (audio-linked pages enqueue clips on first paint and are slower).
    if not wait_for_ccv2_workspace(page, timeout_ms=25000):
        if not _speaker_id_workspace_ready(page):
            wait(page, 2000)


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
    if exact and btn.count() == 0:
        btn = root.get_by_role("button", name=name, exact=False)
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


def _main_button_matching(page: Page, label: str):
    """Locate a main-pane button whose accessible name ends with ``label``.

    Streamlit Material icon buttons expose names like ``chevron_right  Next``.
    """
    root = page.locator('[data-testid="stMain"], section.main').first
    pattern = re.compile(rf"(^|\s){re.escape(label)}$")
    return root.get_by_role("button", name=pattern)


def speaker_id_workspace(page: Page):
    """Locate the CCv2 Speaker ID workspace root (pierces open shadow DOM)."""
    return page.locator(
        '[data-testid="speaker-id-workspace"], .tx-sid-root'
    ).first


def wait_for_ccv2_workspace(page: Page, *, timeout_ms: int = 25000) -> bool:
    """Wait until the CCv2 workspace host and title have painted.

    Returns True when the workspace is ready. Returns False when it never
    mounts (classic fallback / missing ``transcriptx-workspaces``).
    """
    ws = speaker_id_workspace(page)
    try:
        expect(ws).to_be_attached(timeout=timeout_ms)
        expect(ws.locator(".tx-sid-title").first).to_be_visible(timeout=timeout_ms)
        return True
    except Exception:
        return False


def speaker_workspace_text(page: Page) -> str:
    """Return Speaker ID content, including CCv2 shadow-DOM sample lines.

    ``stMain.inner_text`` does not include shadow-tree text, so CCv2 sample
    lines must be read from ``.tx-sid-root`` directly.
    """
    ws = speaker_id_workspace(page)
    if ws.count():
        try:
            text = (ws.inner_text(timeout=10000) or "").strip()
            if text:
                return text
        except Exception:
            pass
    return page_text(page)


def fill_assign_name(page: Page, name: str) -> None:
    """Fill Speaker Identification name field and save (CCv2 or classic)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        inp = ws.locator(".tx-sid-name-input")
        expect(inp.first).to_be_visible(timeout=20000)
        inp.first.click()
        inp.first.fill(name)
        wait(page, 500)
        save = ws.locator(".tx-sid-save")
        expect(save.first).to_be_visible(timeout=10000)
        save.first.click(force=True)
        wait(page, 3500)
        return

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
    save = _main_button_matching(page, "Save name")
    expect(save.first).to_be_visible(timeout=10000)
    save.first.click(force=True)
    wait(page, 3000)


def click_speaker_nav(page: Page, direction: str) -> None:
    """Click Speaker Identification Prev or Next (CCv2 or classic)."""
    label = {"prev": "Prev", "next": "Next"}[direction.lower()]
    ws = speaker_id_workspace(page)
    if ws.count():
        sel = ".tx-sid-next" if label == "Next" else ".tx-sid-prev"
        btn = ws.locator(sel)
        expect(btn.first).to_be_visible(timeout=20000)
        btn.first.click(force=True)
        wait(page, 3000)
        return
    btn = _main_button_matching(page, label)
    expect(btn.first).to_be_visible(timeout=20000)
    btn.first.click(force=True)
    wait(page, 2500)


def click_ignore_speaker(page: Page) -> None:
    """Ignore/toggle the active speaker (CCv2 Ignore or classic Ignore)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        btn = ws.locator(".tx-sid-ignore")
        expect(btn.first).to_be_visible(timeout=20000)
        btn.first.click(force=True)
        wait(page, 3500)
        return
    btn = _main_button_matching(page, "Ignore")
    expect(btn.first).to_be_visible(timeout=20000)
    btn.first.click(force=True)
    wait(page, 3000)


def click_unignore_speaker(page: Page) -> None:
    """Unignore the active speaker (CCv2 Ignore toggle or classic Unignore)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        # CCv2 uses a single Ignore button that toggles ignore state.
        btn = ws.locator(".tx-sid-ignore")
        expect(btn.first).to_be_visible(timeout=20000)
        btn.first.click(force=True)
        wait(page, 3500)
        return
    btn = _main_button_matching(page, "Unignore")
    expect(btn.first).to_be_visible(timeout=20000)
    btn.first.click(force=True)
    wait(page, 3000)


def active_speaker_heading(page: Page) -> str:
    """Return active-speaker title/status (CCv2 title+status or classic heading)."""
    wait_for_ccv2_workspace(page, timeout_ms=20000)
    ws = speaker_id_workspace(page)
    if ws.count():
        title = ws.locator(".tx-sid-title")
        status = ws.locator(".tx-sid-status")
        expect(title.first).to_be_visible(timeout=20000)
        parts = [(title.first.inner_text() or "").strip()]
        if status.count():
            parts.append((status.first.inner_text() or "").strip())
        # Speaker list current button also encodes SPEAKER_XX.
        current = ws.locator('.tx-sid-speaker-btn[aria-current="true"]')
        if current.count():
            parts.append((current.first.inner_text() or "").strip())
        return " · ".join(p for p in parts if p)

    root = page.locator('[data-testid="stMain"], section.main').first
    heading = root.get_by_text(re.compile(r"Speaker\s+\d+\s*/\s*\d+"))
    expect(heading.first).to_be_visible(timeout=20000)
    return (heading.first.inner_text() or "").strip()


def jump_to_speaker_index(page: Page, index: int) -> None:
    """Select a speaker by index (CCv2 speaker list or classic Jump selectbox)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        buttons = ws.locator(".tx-sid-speaker-btn")
        expect(buttons.first).to_be_visible(timeout=20000)
        count = buttons.count()
        if index < 0 or index >= count:
            raise RuntimeError(f"jump index {index} out of range (count={count})")
        buttons.nth(index).click(force=True)
        wait(page, 3500)
        return

    root = page.locator('[data-testid="stMain"], section.main').first
    # Prefer the labeled Jump control; fall back to the last main selectbox.
    jump = root.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Jump to speaker", re.I)
    )
    target = jump.first if jump.count() else root.locator('[data-testid="stSelectbox"]').last
    if target.count() == 0:
        raise RuntimeError("no selectbox found for Jump to speaker")
    target.scroll_into_view_if_needed()
    # Open the listbox via the visible combo / value area.
    combo = target.locator('[data-baseweb="select"], [role="combobox"], input').first
    if combo.count():
        combo.click(force=True)
    else:
        target.click(force=True)
    wait(page, 800)
    options = page.locator('[role="option"]')
    if options.count() == 0:
        # Retry once after a short settle (clip/audio widgets can steal focus).
        wait(page, 1000)
        if combo.count():
            combo.click(force=True)
        else:
            target.click(force=True)
        wait(page, 800)
        options = page.locator('[role="option"]')
    expect(options.first).to_be_visible(timeout=10000)
    count = options.count()
    if index < 0 or index >= count:
        raise RuntimeError(f"jump index {index} out of range (count={count})")
    options.nth(index).click()
    wait(page, 3000)


def play_first_clip(page: Page) -> None:
    """Click the first sample Play control (CCv2 ▶ or classic Play-this-clip)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        play = ws.locator(".tx-sid-sample-play")
        expect(play.first).to_be_visible(timeout=20000)
        play.first.click(force=True)
        wait(page, 4000)
        return

    root = page.locator('[data-testid="stMain"], section.main').first
    # Material icon buttons often expose the icon token as the accessible name.
    candidates = [
        root.get_by_role("button", name=re.compile(r"play", re.I)),
        root.locator('button[title*="Play this clip" i]'),
        root.locator('[data-testid="stTooltipHoverTarget"]').filter(
            has_text=re.compile(r"play", re.I)
        ),
        root.locator("button").filter(has_text=re.compile(r"play_arrow|▶|Play")),
    ]
    clicked = False
    for loc in candidates:
        if loc.count():
            loc.first.click(force=True)
            clicked = True
            break
    if not clicked:
        raise RuntimeError("no Play-this-clip control found on Speaker Identification")
    wait(page, 3500)


def assert_playback_available(page: Page) -> None:
    """Fail if Speaker ID reports missing audio/ffmpeg / playback unavailable."""
    body = speaker_workspace_text(page) + "\n" + page_text(page)
    assert "audio file not found" not in body.lower(), body[:800]
    assert "ffmpeg not found" not in body.lower(), body[:800]
    assert "Playback unavailable" not in body, body[:800]
    assert "Protocol mismatch" not in body, body[:800]


def assert_clip_player_mounted(page: Page) -> None:
    """Assert an audio player is present (CCv2 ``.tx-sid-audio`` or classic)."""
    ws = speaker_id_workspace(page)
    if ws.count():
        audio = ws.locator("audio.tx-sid-audio, audio")
        expect(audio.first).to_be_attached(timeout=20000)
        return
    root = page.locator('[data-testid="stMain"], section.main').first
    audio = root.locator("audio")
    # Streamlit may mount HTML5 audio or an iframe/media wrapper.
    media = root.locator('[data-testid="stAudio"], audio, video')
    expect(audio.first.or_(media.first)).to_be_attached(timeout=20000)



def assert_clip_src_ready(page: Page, *, timeout_ms: int = 20000) -> None:
    """Wait until CCv2 <audio> has a blob: or data: src (clip bytes actually loaded)."""
    page.wait_for_function(
        """() => {
          const srcOf = (audio) => (audio && (audio.currentSrc || audio.src)) || "";
          const ok = (src) => src.startsWith("blob:") || src.startsWith("data:");
          const visit = (el) => {
            if (!el) return false;
            if (el.tagName === "AUDIO" && ok(srcOf(el))) return true;
            const audio = el.querySelector && el.querySelector("audio");
            if (audio && ok(srcOf(audio))) return true;
            const sr = el.shadowRoot;
            if (sr) {
              const a = sr.querySelector("audio");
              if (a && ok(srcOf(a))) return true;
              for (const child of sr.querySelectorAll("*")) {
                if (visit(child)) return true;
              }
            }
            return false;
          };
          for (const el of document.querySelectorAll("*")) {
            if (visit(el)) return true;
          }
          return false;
        }""",
        timeout=timeout_ms,
    )


def click_load_more_samples(page: Page) -> None:
    """Click CCv2 Show N more lines."""
    wait_for_ccv2_workspace(page, timeout_ms=20000)
    ws = speaker_id_workspace(page)
    btn = ws.locator(".tx-sid-load-more")
    expect(btn.first).to_be_attached(timeout=20000)
    try:
        btn.first.scroll_into_view_if_needed()
    except Exception:
        pass
    expect(btn.first).to_be_visible(timeout=10000)
    before_plays = sample_play_count(page)
    before = len((speaker_workspace_text(page) or "").splitlines())
    btn.first.click(force=True)
    deadline = time.time() + 20.0
    after_plays = before_plays
    while time.time() < deadline:
        wait(page, 500)
        after_plays = sample_play_count(page)
        if after_plays > before_plays:
            break
    after = len((speaker_workspace_text(page) or "").splitlines())
    assert after >= before, (
        f"load-more did not grow workspace text lines ({before} -> {after})"
    )
    assert after_plays > before_plays, (
        f"load-more did not add sample play buttons ({before_plays} -> {after_plays})"
    )


def sample_play_count(page: Page) -> int:
    ws = speaker_id_workspace(page)
    return ws.locator(".tx-sid-sample-play").count()

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

    click_main_button(page, "Create group", exact=False)
    wait(page, 3500)


def show_unnamed_speakers_on_transcript(page: Page, *, enabled: bool = True) -> None:
    """Toggle 'Show unnamed speakers' on the Transcript viewer when present."""
    root = page.locator('[data-testid="stMain"], section.main').first
    if "Show unnamed speakers" not in (root.inner_text() or ""):
        return
    set_checkbox_labeled(page, "Show unnamed speakers", checked=enabled)


def open_correct_mode_and_propose(
    page: Page,
    *,
    find_text: str,
    replacement: str,
) -> None:
    """Enable Correct mode on Transcript and propose a manual correction."""
    # Planning-review speakers are still SPEAKER_* placeholders; Correct-mode
    # propose panels only render for *visible* segments.
    show_unnamed_speakers_on_transcript(page, enabled=True)
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


def advance_speaker_id_next(page: Page) -> None:
    """Click Next on Speaker Identification to move to the next diarized speaker."""
    click_speaker_nav(page, "next")


def assign_speaker_name(page: Page, name: str, *, advance: bool = False) -> None:
    """Fill Assign name, save, and optionally advance to the next speaker."""
    fill_assign_name(page, name)
    if advance:
        advance_speaker_id_next(page)


def select_run_analysis_target(page: Page, target: str) -> None:
    """Set Run Analysis target to Transcript or Group via segmented control."""
    root = page.locator('[data-testid="stMain"], section.main').first
    control = root.get_by_role("button", name=target, exact=True)
    if control.count() == 0:
        control = root.get_by_text(target, exact=True)
    expect(control.first).to_be_visible(timeout=20000)
    control.first.click(force=True)
    wait(page, 2000)


def select_group_on_run_analysis(page: Page, group_name: str) -> None:
    """Pick a group from Run Analysis when target is Group."""
    root = page.locator('[data-testid="stMain"], section.main').first
    boxes = root.locator('[data-testid="stSelectbox"]')
    expect(boxes.first).to_be_visible(timeout=20000)
    boxes.first.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=group_name)
    expect(opt.first).to_be_visible(timeout=10000)
    opt.first.click()
    wait(page, 2500)


def open_artifacts_preview(page: Page) -> None:
    """Switch Artifacts to Preview and confirm the section renders."""
    nav(page, "Artifacts")
    wait(page, 2500)
    click_section_tab(page, "Preview")
    wait(page, 2000)


def open_corrections_studio_from_viewer(page: Page) -> bool:
    """Open Corrections Studio from Transcript Correct mode when offered."""
    for label in ("Corrections Studio", "Open Studio"):
        link = page.get_by_role("button", name=label, exact=False)
        if link.count() == 0:
            link = page.get_by_text(label, exact=False)
        if link.count():
            try:
                link.first.click(force=True)
                wait(page, 3500)
                return True
            except Exception:
                continue
    return False


def open_speaker_profile(page: Page, name: str) -> None:
    """Select a longitudinal speaker profile on the Speakers page."""
    nav(page, "Speakers")
    wait(page, 2500)
    # Profiles may render as selectbox options, table rows, or detail cards.
    boxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
    if boxes.count():
        boxes.first.click()
        wait(page, 800)
        opt = page.locator('[role="option"]').filter(has_text=name)
        if opt.count() == 0:
            opt = page.locator('[role="option"]').filter(has_text=name.split()[0])
        if opt.count():
            opt.first.click()
            wait(page, 3000)
            return
    row = page.get_by_text(name, exact=False)
    if row.count():
        row.first.click(force=True)
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
