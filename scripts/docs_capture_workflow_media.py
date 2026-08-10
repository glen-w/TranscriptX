#!/usr/bin/env python3
"""Capture workflow walkthrough media from a live TranscriptX UI."""

from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://127.0.0.1:8501"
OUT = Path("/workspace/.local/workflow_media/raw")
FINAL = Path("/workspace/docs/_static/workflows")
VIEWPORT = {"width": 1440, "height": 900}


def wait(page: Page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)


def sidebar(page: Page):
    return page.locator('[data-testid="stSidebar"]')


def nav(page: Page, label: str) -> None:
    sb = sidebar(page)
    btn = sb.get_by_role("button", name=label, exact=True)
    btn.first.click(force=True, timeout=20000)
    wait(page, 3500)


def select_transcript(page: Page, needle: str = "planning_review") -> None:
    """Select transcript via Library page dropdown or sidebar picker."""
    nav(page, "Library")
    # Main pane select
    boxes = page.locator('[data-testid="stSelectbox"]')
    print("selectboxes", boxes.count())
    target = None
    for i in range(boxes.count()):
        txt = boxes.nth(i).inner_text()
        if "Select transcript" in txt or "Select a transcript" in txt or i == boxes.count() - 1:
            target = boxes.nth(i)
    if target is None and boxes.count():
        target = boxes.first
    if target is None:
        raise RuntimeError("no selectbox found")
    target.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text=needle)
    if opt.count() == 0:
        # list all
        print("options", page.locator('[role="option"]').all_text_contents())
        opt = page.locator('[role="option"]').filter(has_text="planning")
    opt.first.click()
    wait(page, 3000)
    # Also set sidebar picker if present
    sb_boxes = sidebar(page).locator('[data-testid="stSelectbox"]')
    if sb_boxes.count():
        sb_boxes.first.click()
        wait(page, 600)
        opt2 = page.locator('[role="option"]').filter(has_text=needle)
        if opt2.count():
            opt2.first.click()
            wait(page, 2000)


def shot(page: Page, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    if not name.endswith(".png"):
        name = f"{name}.png"
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    print("wrote", path, path.stat().st_size)
    return path


def make_gif(pattern: str, out_name: str) -> None:
    frames = sorted(OUT.glob(pattern))
    if len(frames) < 2:
        print("skip gif", out_name, "frames", len(frames))
        return
    tmp = OUT / out_name
    subprocess.run(
        ["convert", "-delay", "50", "-loop", "0", *[str(f) for f in frames], str(tmp)],
        check=False,
    )
    if not tmp.exists():
        return
    dest = FINAL / out_name
    subprocess.run(
        ["gifsicle", "-O3", "--colors", "128", "-o", str(dest), str(tmp)],
        check=False,
    )
    if not dest.exists():
        dest.write_bytes(tmp.read_bytes())
    print("gif", dest, dest.stat().st_size)


def promote_png(name: str) -> None:
    src = OUT / name
    if not src.exists():
        print("missing", name)
        return
    dest = FINAL / name
    # compress copy
    subprocess.run(
        ["pngquant", "--quality=65-85", "--force", "--output", str(dest), str(src)],
        check=False,
    )
    if not dest.exists():
        dest.write_bytes(src.read_bytes())
    subprocess.run(["optipng", "-o2", str(dest)], check=False)
    print("png", dest, dest.stat().st_size)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FINAL.mkdir(parents=True, exist_ok=True)
    (OUT / "gif_frames_run").mkdir(exist_ok=True)
    (OUT / "gif_frames_speaker").mkdir(exist_ok=True)
    (OUT / "gif_frames_jump").mkdir(exist_ok=True)
    (OUT / "gif_frames_export").mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        wait(page, 5000)

        # Import page
        nav(page, "Import Transcript")
        shot(page, "first-analysis-import.png")

        # Select transcript for subsequent pages
        select_transcript(page)

        # Run Analysis
        nav(page, "Run Analysis")
        shot(page, "first-analysis-run-analysis.png")
        shot(page, "local-ai-llm-setup.png")
        for i in range(5):
            page.screenshot(path=str(OUT / f"gif_frames_run/frame_{i:02d}.png"))
            page.wait_for_timeout(350)

        # Overview
        nav(page, "Overview")
        wait(page, 2000)
        shot(page, "first-analysis-overview.png")
        shot(page, "investigate-overview.png")
        shot(page, "local-ai-overview-summary.png")

        # Speaker Identification
        nav(page, "Speaker Identification")
        shot(page, "speaker-trust-page.png")
        for i in range(5):
            page.screenshot(path=str(OUT / f"gif_frames_speaker/frame_{i:02d}.png"))
            nxt = page.get_by_role("button", name="Next →")
            if nxt.count():
                try:
                    nxt.first.click(force=True)
                    wait(page, 900)
                except Exception:
                    page.wait_for_timeout(400)
            else:
                page.wait_for_timeout(400)

        # Transcript
        # Prefer VIEW transcript button - second "Transcript" in sidebar view section
        nav(page, "Transcript")
        shot(page, "speaker-trust-transcript.png")

        # Insights
        nav(page, "Insights")
        for label in ("Highlights", "Actions", "Summary"):
            tab = page.get_by_role("button", name=label, exact=True)
            if tab.count() == 0:
                tab = page.get_by_text(label, exact=True)
            if tab.count():
                try:
                    tab.first.click(force=True)
                    wait(page, 2000)
                except Exception as exc:
                    print("tab fail", label, exc)
            if label == "Highlights":
                shot(page, "investigate-highlights.png")
                for i in range(4):
                    page.screenshot(path=str(OUT / f"gif_frames_jump/frame_{i:02d}.png"))
                    jump = page.get_by_text("Jump to transcript", exact=False)
                    if jump.count():
                        try:
                            jump.first.click(force=True)
                            wait(page, 2000)
                            page.screenshot(
                                path=str(OUT / f"gif_frames_jump/frame_{i:02d}_after.png")
                            )
                            break
                        except Exception:
                            pass
                    page.wait_for_timeout(400)
            if label == "Actions":
                shot(page, "local-ai-meeting-extracts.png")

        # Artifacts
        nav(page, "Artifacts")
        for label in ("Browse", "Export"):
            tab = page.get_by_role("button", name=label, exact=True)
            if tab.count() == 0:
                tab = page.get_by_text(label, exact=True)
            if tab.count():
                try:
                    tab.first.click(force=True)
                    wait(page, 2000)
                except Exception as exc:
                    print("artifacts tab", label, exc)
            if label == "Browse":
                shot(page, "export-artifacts-browse.png")
            if label == "Export":
                shot(page, "export-panel.png")
                for i in range(4):
                    page.screenshot(path=str(OUT / f"gif_frames_export/frame_{i:02d}.png"))
                    create = page.get_by_role("button", name="Create Export")
                    if create.count():
                        try:
                            create.first.click(force=True)
                            wait(page, 2500)
                        except Exception:
                            pass
                    page.wait_for_timeout(400)

        browser.close()

    make_gif("gif_frames_run/frame_*.png", "first-analysis-run-complete.gif")
    make_gif("gif_frames_speaker/frame_*.png", "speaker-trust-naming.gif")
    make_gif("gif_frames_jump/frame_*.png", "investigate-evidence-jump.gif")
    make_gif("gif_frames_export/frame_*.png", "export-download.gif")

    for name in [
        "first-analysis-import.png",
        "first-analysis-run-analysis.png",
        "first-analysis-overview.png",
        "speaker-trust-page.png",
        "speaker-trust-transcript.png",
        "investigate-overview.png",
        "investigate-highlights.png",
        "local-ai-llm-setup.png",
        "local-ai-overview-summary.png",
        "local-ai-meeting-extracts.png",
        "export-artifacts-browse.png",
        "export-panel.png",
    ]:
        promote_png(name)

    print("done")


if __name__ == "__main__":
    main()
