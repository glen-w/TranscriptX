"""Shared CSS and page shell for self-contained export index HTML."""

from __future__ import annotations

import base64
import html
from pathlib import Path

# Light-surface wordmark (navy on transparent). Resolved from the packaged web
# assets without importing the Streamlit shell.
_LOGO_PATH = (
    Path(__file__).resolve().parents[1] / "web" / "assets" / "transcriptx_logo.png"
)
_WORDMARK_CACHE: str | None = None

# Shared inline CSS for self-contained export index pages (charts gallery and the
# combined Overview export index). Kept renderer-agnostic and CDN-free so exports
# render correctly when opened directly from disk over file://.
EXPORT_INDEX_CSS = (
    "body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    "background:#f6f7f9;color:#15171a;}main{display:grid;grid-template-columns:280px 1fr;"
    "gap:28px;max-width:1440px;margin:0 auto;padding:32px;}"
    "nav{box-sizing:border-box;position:sticky;top:16px;align-self:start;display:flex;"
    "flex-direction:column;max-height:calc(100vh - 32px);overflow:hidden;background:#fff;"
    "border:1px solid #dde2e8;border-radius:10px;padding:16px 18px;}"
    ".tx-nav-head{flex:0 0 auto;margin:0 0 12px;padding-bottom:12px;border-bottom:1px solid #eef1f5;}"
    ".tx-wordmark{display:block;width:100%;max-width:200px;height:auto;}"
    ".tx-wordmark-text{font-weight:700;font-size:18px;color:#0f3d91;letter-spacing:-0.02em;}"
    ".tx-nav-label{display:block;margin:12px 0 0;}"
    ".tx-nav-scroll{overflow-y:auto;min-height:0;overscroll-behavior:contain;}"
    "nav ul{margin:8px 0 0;padding-left:18px;}"
    "nav li{margin:7px 0;line-height:1.4;}"
    "nav li.nav-heading{list-style:none;margin:18px 0 6px -18px;}"
    "nav a{text-decoration:none;color:#0f3d91;}"
    ".content h1{margin:0 0 20px;}.notice{background:#fff7db;border:1px solid #f0d37a;"
    "padding:12px 14px;border-radius:8px;margin-bottom:18px;}.card-grid{display:grid;"
    "grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;}.card{background:#fff;"
    "border:1px solid #dde2e8;border-radius:10px;padding:14px;display:flex;flex-direction:column;"
    "gap:10px;}.card h3{margin:0;font-size:16px;}.meta{margin:0;color:#5a6473;font-size:13px;}"
    ".chart-desc{margin:0;color:#5a6473;font-size:13px;line-height:1.45;}"
    ".chart-narrative{margin:0;color:#1f2933;font-size:13px;line-height:1.5;"
    "padding-top:4px;border-top:1px solid #eef1f5;}"
    ".card img{width:100%;height:auto;max-width:100%;border-radius:8px;border:1px solid #e6eaf0;display:block;}"
    ".chart-thumb{display:block;cursor:zoom-in;}.chart-thumb:hover img{border-color:#0f3d91;"
    "box-shadow:0 0 0 2px rgba(15,61,145,0.15);}"
    ".badge{display:inline-block;width:max-content;padding:2px 8px;border-radius:999px;"
    "background:#e8eefc;color:#123b8c;font-size:12px;}.open-link{font-size:13px;font-weight:600;}"
    ".card iframe{width:100%;height:320px;border:1px solid #e1e6ee;border-radius:8px;}"
    ".hint{font-size:12px;color:#5a6473;margin:0;}section{margin-bottom:40px;}"
    ".tx-segment{background:#fff;border:1px solid #dde2e8;border-radius:10px;padding:14px 16px;"
    "margin-bottom:14px;}.tx-speaker-chip{display:inline-block;padding:2px 10px;border-radius:999px;"
    "background:#e8eefc;color:#123b8c;font-weight:600;font-size:13px;}.tx-time{color:#5a6473;"
    "font-size:12px;margin-left:8px;}.tx-text{margin:8px 0 0;white-space:pre-wrap;line-height:1.5;}"
    ".tx-summary{background:#fff;border:1px solid #dde2e8;border-radius:10px;padding:16px 18px;"
    "margin-bottom:16px;}"
    ".tx-summary-body{font-size:14px;line-height:1.55;color:#15171a;}"
    ".tx-summary-body p{margin:0 0 10px;}.tx-summary-body p:last-child{margin-bottom:0;}"
    ".tx-summary-body h3{margin:14px 0 8px;font-size:15px;}.tx-summary-body h3:first-child{margin-top:0;}"
    ".tx-summary-body h4{margin:12px 0 6px;font-size:14px;}"
    ".tx-summary-body ul,.tx-summary-body ol{margin:0 0 10px;padding-left:1.35em;}"
    ".tx-summary-body li{margin:3px 0;}.tx-summary-body ul ul,.tx-summary-body ol ul,"
    ".tx-summary-body ul ol,.tx-summary-body ol ol{margin:4px 0;}"
    ".tx-summary-body code{font-size:0.92em;background:#f0f3f7;padding:1px 4px;border-radius:4px;}"
    ".included-files{font-size:13px;color:#5a6473;}.included-files ul{margin:6px 0 0;padding-left:18px;}"
    "@media (max-width: 900px){main{grid-template-columns:1fr;padding:20px;}"
    "nav{position:static;max-height:none;}.tx-nav-scroll{max-height:50vh;}}"
)


def render_wordmark_html(logo_path: Path | None = None) -> str:
    """Inline the TranscriptX wordmark, or the product name when the file is absent.

    The default packaged logo is cached. Pass ``logo_path`` to render a specific
    file (used by tests); that path is not cached.
    """
    if logo_path is not None:
        return _wordmark_markup(logo_path)
    global _WORDMARK_CACHE
    if _WORDMARK_CACHE is None:
        _WORDMARK_CACHE = _wordmark_markup(_LOGO_PATH)
    return _WORDMARK_CACHE


def _wordmark_markup(path: Path) -> str:
    if path.is_file():
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return (
            '<img class="tx-wordmark" alt="TranscriptX" '
            f'src="data:image/png;base64,{encoded}" />'
        )
    return '<span class="tx-wordmark-text">TranscriptX</span>'


def omitted_charts_banner(omitted_count: int) -> str:
    """Return the yellow notice banner when charts were omitted, or empty string."""
    if omitted_count <= 0:
        return ""
    plural = "s" if omitted_count != 1 else ""
    return (
        '<div class="notice">'
        f"{omitted_count} chart{plural} were unavailable and omitted from this export."
        "</div>"
    )


def wrap_export_page(
    title: str,
    nav_html: str,
    content_html: str,
    *,
    nav_label: str = "Contents",
    heading: str | None = None,
) -> str:
    """Wrap nav + content in the shared export index document shell."""
    page_heading = heading if heading is not None else title
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>{html.escape(title)}</title>"
        "<style>" + EXPORT_INDEX_CSS + "</style></head><body>"
        "<main><nav><div class='tx-nav-head'>"
        + render_wordmark_html()
        + f"<strong class='tx-nav-label'>{html.escape(nav_label)}</strong></div>"
        "<div class='tx-nav-scroll'><ul>"
        + nav_html
        + "</ul></div></nav><div class='content'>"
        f"<h1>{html.escape(page_heading)}</h1>"
        + content_html
        + "</div></main></body></html>"
    )
