"""Light coverage for 0.9.7 harden + public-surfaces scaffolding."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Landing gallery copies of README / Sphinx stills (website/README.md).
WEBSITE_SCREENSHOT_PAIRS = (
    ("home.png", "home.png"),
    ("speaker-id.png", "speaker-identification-page.png"),
    ("corrections-studio.png", "corrections-studio.png"),
    ("run-analysis.png", "first-analysis-run-analysis.png"),
    ("overview.png", "first-analysis-overview.png"),
    ("transcript.png", "speaker-identification-transcript.png"),
    ("insights.png", "investigate-highlights.png"),
    ("charts-gallery.png", "charts-gallery.png"),
)

_INSTALL_MARKERS = (
    ".env.example",
    "HOST_RECORDINGS_DIR",
    "docker compose up transcriptx-web",
)


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project and stripped.startswith("version"):
            _, _, rhs = line.partition("=")
            return rhs.split("#", 1)[0].strip().strip('"').strip("'")
    raise AssertionError("no version = under [project] in pyproject.toml")


def _readme_outcome_bullets(readme: str) -> list[str]:
    match = re.search(
        r"## What can I do with it\?\n\n((?:- .+\n)+)",
        readme,
    )
    assert match, "README is missing the What can I do bullet list"
    return [line[2:].strip() for line in match.group(1).splitlines() if line.startswith("- ")]


def _website_outcome_bullets(html: str) -> list[str]:
    match = re.search(
        r'<ul class="outcomes">\s*((?:<li>[\s\S]+?</li>\s*)+)</ul>',
        html,
    )
    assert match, "website is missing <ul class=\"outcomes\">"
    return [
        re.sub(r"<[^>]+>", "", item).strip()
        for item in re.findall(r"<li>([\s\S]+?)</li>", match.group(1))
    ]


def _toctree_workflow_stems(index_md: str) -> set[str]:
    stems: set[str] = set()
    for match in re.finditer(r"^workflows/([a-z0-9-]+)\s*$", index_md, re.M):
        stem = match.group(1)
        if stem != "index":
            stems.add(stem)
    return stems


@pytest.mark.unit
def test_website_landing_scaffold() -> None:
    index = ROOT / "website" / "index.html"
    css = ROOT / "website" / "styles.css"
    chrome_css = ROOT / "website" / "chrome" / "site_chrome.css"
    chrome_js = ROOT / "website" / "chrome" / "site_nav.js"
    pages = ROOT / ".github" / "workflows" / "pages.yml"
    assert index.is_file()
    assert css.is_file()
    assert chrome_css.is_file()
    assert chrome_js.is_file()
    assert pages.is_file()
    html = index.read_text(encoding="utf-8")
    assert "TranscriptX" in html
    assert 'class="site-header tx-site-chrome"' in html
    assert "chrome/site_chrome.css" in html
    assert "chrome/site_nav.js" in html
    assert "./guide/workflows/index.html" in html
    assert "./guide/runtime/transcription.html" in html
    assert "./guide/" in html
    # Forbidden public RTD hostname must stay out of marketing copy until go-live.
    forbidden = "readthedocs" + ".io"
    assert forbidden not in html
    assert "ko-fi.com/C0C1XK8G" in html
    assert "website" in pages.read_text(encoding="utf-8")


@pytest.mark.unit
def test_sphinx_guide_keeps_site_header_chrome() -> None:
    """Guide pages (incl. workflows) must keep the public site header nav."""
    conf = (ROOT / "docs" / "conf.py").read_text(encoding="utf-8")
    assert "../website/chrome" in conf
    assert "site_chrome.css" in conf
    assert "site_nav.js" in conf
    page_tmpl = (ROOT / "docs" / "_templates" / "page.html").read_text(
        encoding="utf-8"
    )
    assert "tx-site-chrome" in page_tmpl
    assert "workflows/index" in page_tmpl
    assert "pathto(master_doc)" in page_tmpl
    chrome_css = (ROOT / "website" / "chrome" / "site_chrome.css").read_text(
        encoding="utf-8"
    )
    assert "body:has(.tx-site-chrome) .sidebar-brand" in chrome_css
    assert "body:has(.tx-site-chrome) .mobile-header .header-center" in chrome_css


@pytest.mark.unit
def test_website_footer_version_matches_pyproject() -> None:
    html = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    match = re.search(r"Version\s+(\d+\.\d+\.\d+(?:\.\d+)?)", html)
    assert match, "website footer is missing Version X.Y.Z"
    assert match.group(1) == _project_version()


@pytest.mark.unit
def test_readme_and_website_outcome_bullets_match() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    readme_bullets = _readme_outcome_bullets(readme)
    website_bullets = _website_outcome_bullets(html)
    assert len(readme_bullets) == 6
    assert readme_bullets == website_bullets


@pytest.mark.unit
def test_readme_and_website_docker_install_markers() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    for surface, text in (("README", readme), ("website", html)):
        for marker in _INSTALL_MARKERS:
            assert marker in text, f"{surface} is missing {marker!r}"
        assert "cp .env.example .env" in text, f"{surface} is missing .env.example → .env copy"


@pytest.mark.unit
def test_website_screenshots_match_docs_stills() -> None:
    website_dir = ROOT / "website" / "images"
    docs_dir = ROOT / "docs" / "_static" / "workflows"
    for website_name, docs_name in WEBSITE_SCREENSHOT_PAIRS:
        website_path = website_dir / website_name
        docs_path = docs_dir / docs_name
        assert website_path.is_file(), website_path
        assert docs_path.is_file(), docs_path
        website_digest = hashlib.sha256(website_path.read_bytes()).hexdigest()
        docs_digest = hashlib.sha256(docs_path.read_bytes()).hexdigest()
        assert website_digest == docs_digest, f"{website_name} drifted from {docs_name}"


@pytest.mark.unit
def test_sphinx_toctrees_cover_workflow_pages() -> None:
    index_md = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    listed = _toctree_workflow_stems(index_md)
    files = {
        path.stem
        for path in (ROOT / "docs" / "workflows").glob("*.md")
        if path.name != "index.md"
    }
    assert listed == files, f"toctree missing {files - listed} extra {listed - files}"


@pytest.mark.unit
def test_notice_and_issue_templates_exist() -> None:
    assert (ROOT / "NOTICE").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").is_file()


@pytest.mark.unit
def test_audit_judgements_and_rtd_checklist() -> None:
    judgements = (
        ROOT / "docs" / "dev" / "analysis_quality_audit_judgements.md"
    ).read_text(encoding="utf-8")
    assert "`highlights`" in judgements
    assert "`llm_summary`" in judgements
    assert "Local AI" in judgements or "must-fix" in judgements
    checklist = (ROOT / "docs" / "dev" / "rtd_go_live_checklist.md").read_text(
        encoding="utf-8"
    )
    assert "stale_refs" in checklist


@pytest.mark.unit
def test_llm_surface_badges_include_local_ai() -> None:
    from transcriptx.web.blocks.llm_presentation import (
        AI_OUTPUT_BADGE,
        llm_surface_badges,
        provenance_badges,
    )

    assert AI_OUTPUT_BADGE == "Local AI"
    assert llm_surface_badges(None) == [AI_OUTPUT_BADGE]
    assert llm_surface_badges({"model": "m", "provider": "ollama"}) == [
        AI_OUTPUT_BADGE,
        "m",
        "ollama",
    ]
    assert provenance_badges({"model": "m"}) == ["m"]


@pytest.mark.unit
def test_perf_envelope_recipe_script() -> None:
    script = ROOT / "scripts" / "release" / "perf_envelope_recipe.py"
    assert script.is_file()
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "perf-envelopes" in makefile
    assert "perf_envelope_recipe.py" in makefile


@pytest.mark.unit
def test_voice_privacy_notice_v2() -> None:
    from transcriptx.core.speaker_profiles.voice.privacy import (
        PRIVACY_NOTICE_VERSION,
        VOICE_PRIVACY_USER_NOTICE,
    )

    assert PRIVACY_NOTICE_VERSION == "voice_privacy_notice.v2"
    assert "speaker-identity" in VOICE_PRIVACY_USER_NOTICE
    assert "embeddings" in VOICE_PRIVACY_USER_NOTICE.lower()
