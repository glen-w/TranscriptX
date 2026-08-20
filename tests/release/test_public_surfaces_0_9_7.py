"""Light coverage for 0.9.7 harden + public-surfaces scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


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
