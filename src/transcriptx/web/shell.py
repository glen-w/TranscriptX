"""
Streamlit shell: page config and global styles.

Kept separate from ``app.py`` so the entry module focuses on routing and pages.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# Packaged under the web module so Docker (src mount / wheel install) can find them.
# Repo-root ``assets/`` stays the docs/marketing copy; do not resolve via PROJECT_ROOT
# (in containers that points at site-packages parent, not the git checkout).
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_LOGO_ICON = _ASSETS_DIR / "transcriptx_icon.png"
_LOGO_FULL = _ASSETS_DIR / "transcriptx_logo.png"
_LOGO_DARK = _ASSETS_DIR / "transcriptx_logo_dark.png"
_FAVICON = _ASSETS_DIR / "favicon.ico"


def brand_logo_path(*, for_dark_chrome: bool = True) -> Path | None:
    """Sidebar/brand mark path.

    Prefer the light-wordmark variant on dark Streamlit chrome; fall back to the
    standard full logo, then icon-only.
    """
    if for_dark_chrome and _LOGO_DARK.is_file():
        return _LOGO_DARK
    if _LOGO_FULL.is_file():
        return _LOGO_FULL
    if _LOGO_ICON.is_file():
        return _LOGO_ICON
    return None


def configure_streamlit_page() -> None:
    """``st.set_page_config`` must run before other Streamlit commands."""
    page_icon = str(_FAVICON) if _FAVICON.is_file() else "🎙️"
    st.set_page_config(
        page_title="TranscriptX",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_global_styles() -> None:
    """Inject shared CSS and scroll-to-top behavior."""
    st.markdown(
        """
<style>
    /* Sidebar width — 256–264px; truncate long values */
    section[data-testid="stSidebar"] {
        min-width: 256px !important;
        max-width: 264px !important;
        width: 260px !important;
    }
    /* Tighten Streamlit's reserved collapse-header strip above brand */
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
        height: 2rem !important;
        min-height: 2rem !important;
        margin-bottom: 0.15rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] * {
        overflow-wrap: anywhere;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="select"] span {
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
        max-width: 100%;
    }
    /* Global left alignment for main content */
    section[data-testid="stAppViewContainer"] .block-container,
    section[data-testid="stAppViewContainer"] .element-container {
        text-align: left;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
        text-align: left;
    }
    .stat-card {
        background-color: var(--secondary-background-color, #262730);
        color: var(--text-color, #fafafa);
        border: 1px solid rgba(250, 250, 250, 0.12);
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: left;
    }
    .stat-card strong,
    .stat-card span {
        color: inherit;
    }
    .speaker-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    .tx-speaker-card-title,
    .tx-speaker-heading {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin: 0.1rem 0 0.35rem 0;
        padding-left: 0.65rem;
        border-left: 4px solid var(--speaker-accent, #5b8def);
        flex-wrap: wrap;
    }
    .tx-speaker-card-title strong,
    .tx-speaker-heading strong {
        color: var(--speaker-accent, #5b8def);
        font-size: 1.05rem;
        letter-spacing: 0.01em;
    }
    a.tx-speaker-profile-link {
        color: inherit;
        text-decoration: none;
        cursor: pointer;
    }
    a.tx-speaker-profile-link:hover,
    a.tx-speaker-profile-link:focus-visible {
        text-decoration: underline;
        text-underline-offset: 0.12em;
    }
    a.tx-speaker-profile-link strong {
        color: inherit;
    }
    .tx-speaker-heading-meta {
        color: #6b7c90;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .tx-speaker-swatch {
        width: 0.65rem;
        height: 0.65rem;
        border-radius: 999px;
        background: var(--speaker-accent, #5b8def);
        flex-shrink: 0;
        display: inline-block;
    }
    .tx-speaker-avatar {
        width: var(--tx-avatar-size, 40px);
        height: var(--tx-avatar-size, 40px);
        border-radius: 999px;
        background: var(--speaker-accent, #5b8def);
        color: #fff;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        overflow: hidden;
        vertical-align: middle;
        line-height: 1;
        font-size: calc(var(--tx-avatar-size, 40px) * 0.38);
        font-weight: 700;
    }
    .tx-speaker-avatar-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .tx-speaker-avatar-initials {
        user-select: none;
    }
    .tx-speaker-expander-swatch {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 2.4rem;
    }
    .tx-speaker-inline {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        margin-right: 0.15rem;
    }
    .tx-speaker-inline strong {
        color: var(--speaker-accent, #5b8def);
    }
    /* Navigation section headers */
    .nav-section-header,
    .subject-section-header {
        display: block;
        font-size: 0.8rem !important;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a9ab0;
        margin: 0.85rem 0 0.15rem 0.1rem !important;
        padding: 0.55rem 0 0.45rem 0 !important;
        line-height: 1.2;
        user-select: none;
    }
    /* Extra breathing room around section labels (Streamlit zeros p margins) */
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.subject-section-header),
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.nav-section-header) {
        margin-top: 0.55rem !important;
        margin-bottom: 0.25rem !important;
        padding-top: 0.15rem !important;
        padding-bottom: 0.15rem !important;
    }
    /* Sidebar nav density — denser than Streamlit defaults, with readable gaps */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] {
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        min-height: 2.15rem !important;
        height: auto !important;
        line-height: 1.3 !important;
    }
    /* Sidebar nav — solid buttons (readable on dark theme) */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"] {
        background: rgba(250, 250, 250, 0.07) !important;
        border: 1px solid rgba(250, 250, 250, 0.14) !important;
        border-radius: 6px !important;
        color: #d7dee8 !important;
        text-align: center;
        padding: 0.35rem 0.55rem;
        font-weight: 500;
        font-size: 0.9rem;
        box-shadow: none !important;
        width: 100%;
        opacity: 1 !important;
        transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"]:hover {
        color: #eef4fb !important;
        background: rgba(31, 119, 180, 0.22) !important;
        border-color: rgba(155, 208, 245, 0.35) !important;
        text-decoration: none;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"]:focus-visible {
        outline: 2px solid #1f77b4;
        outline-offset: 2px;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"]:disabled {
        background: rgba(250, 250, 250, 0.05) !important;
        border-color: rgba(250, 250, 250, 0.10) !important;
        color: #b8c2d0 !important;
        opacity: 1 !important;
    }
    /* Active nav — brighter fill, same size/spacing as inactive */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {
        background: rgba(31, 119, 180, 0.38) !important;
        border: 1px solid rgba(155, 208, 245, 0.45) !important;
        border-radius: 6px !important;
        color: #f3f9fd !important;
        text-align: center;
        padding: 0.35rem 0.55rem;
        font-weight: 600;
        font-size: 0.9rem;
        box-shadow: none !important;
        width: 100%;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: rgba(31, 119, 180, 0.48) !important;
        border-color: rgba(155, 208, 245, 0.55) !important;
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:focus-visible {
        outline: 2px solid #1f77b4;
        outline-offset: 2px;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button p,
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button span {
        color: inherit !important;
    }
    /* Scroll to top button */
    #scroll-to-top-btn {
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        background-color: #1f77b4;
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 24px;
        cursor: pointer;
        display: none;
        z-index: 1000;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    #scroll-to-top-btn:hover {
        background-color: #0d5a8a;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
    }
    #scroll-to-top-btn.show {
        display: block;
    }
    /* Run Analysis sticky footer — keyed via .tx-run-analysis-footer flag */
    .main .block-container {
        padding-bottom: 5.5rem;
    }
    div[data-testid="stVerticalBlock"]:has(> div.tx-run-analysis-footer),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.tx-run-analysis-footer) {
        position: sticky;
        bottom: 0;
        z-index: 60;
        margin-top: 1rem;
        padding: 0.65rem 0.85rem 0.75rem 0.85rem;
        background: var(--background-color, #0e1117);
        border-top: 1px solid rgba(250, 250, 250, 0.12);
        box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.18);
    }
    .tx-run-analysis-footer-summary {
        font-size: 0.85rem;
        color: #8a9ab0;
        line-height: 1.35;
        word-break: break-word;
    }
    .tx-run-analysis-footer-summary .tx-ellipsis {
        display: inline-block;
        max-width: min(28ch, 42vw);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        vertical-align: bottom;
    }
    /* Context bar — single quiet orientation line; rule matches st.divider */
    .tx-context-bar-wrap {
        position: sticky;
        top: 0;
        z-index: 50;
        margin: 0 0 0.5rem 0;
        padding: 0.2rem 0 0.45rem 0;
        background: var(--background-color, transparent);
        border-bottom: 1px solid rgba(250, 250, 250, 0.1);
    }
    .tx-context-bar-inner {
        line-height: 1.4;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.25rem;
    }
    .tx-context-line {
        font-size: 0.76rem;
        font-weight: 400;
        color: #8a9ab0;
        letter-spacing: 0.01em;
    }
    /* Run ID info control — custom hover + focus tooltips */
    .tx-run-id-info {
        position: relative;
        display: inline-flex;
        align-items: center;
        vertical-align: middle;
    }
    .tx-run-id-info-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.15rem;
        height: 1.15rem;
        padding: 0;
        margin: 0;
        border: none;
        border-radius: 50%;
        background: transparent;
        color: #8a9ab0;
        font-size: 0.78rem;
        line-height: 1;
        cursor: help;
    }
    .tx-run-id-info-btn:hover,
    .tx-run-id-info-btn:focus {
        color: #1f77b4;
    }
    .tx-run-id-info-btn:focus-visible {
        outline: 2px solid #1f77b4;
        outline-offset: 2px;
    }
    .tx-run-id-info-tip {
        position: absolute;
        left: 50%;
        bottom: calc(100% + 0.35rem);
        transform: translateX(-50%);
        min-width: 10rem;
        max-width: 22rem;
        padding: 0.35rem 0.5rem;
        border-radius: 6px;
        background: #2c3e50;
        color: #f8fafc;
        font-size: 0.72rem;
        line-height: 1.35;
        word-break: break-all;
        white-space: normal;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
        z-index: 80;
        transition: opacity 0.12s ease;
    }
    .tx-run-id-info:hover .tx-run-id-info-tip,
    .tx-run-id-info:focus-within .tx-run-id-info-tip,
    .tx-run-id-info-btn:focus + .tx-run-id-info-tip,
    .tx-run-id-info-btn:focus-visible + .tx-run-id-info-tip {
        opacity: 1;
        visibility: visible;
    }
    /* Multi-line methodology / help tips (reuse run-id info control) */
    .tx-methodology-info {
        margin-left: 0.35rem;
    }
    .tx-methodology-info-tip {
        left: 0;
        transform: none;
        bottom: auto;
        top: calc(100% + 0.35rem);
        min-width: 16rem;
        max-width: 28rem;
        padding: 0.5rem 0.65rem;
        word-break: normal;
        overflow-wrap: anywhere;
        text-align: left;
    }
    .tx-trends-heading,
    .tx-section-info-heading {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        margin: 0.75rem 0 0.35rem;
    }
    .tx-trends-heading h4,
    .tx-section-info-heading h4 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
    }
    /* Badges (page shell + inline) */
    span.tx-badge {
        display: inline-block;
        padding: 0.12rem 0.45rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #eef2f6;
        color: #3d5166;
        margin-right: 0.35rem;
        margin-bottom: 0.2rem;
        vertical-align: middle;
    }
    /* Page shell title row */
    .tx-page-shell-title {
        font-size: 1.65rem;
        font-weight: 700;
        color: #1f77b4;
        margin: 0 0 0.25rem 0;
        line-height: 1.2;
    }
    .tx-page-shell-desc {
        font-size: 0.92rem;
        color: #5a6b7d;
        margin: 0 0 0.75rem 0;
        max-width: 52rem;
    }
    .tx-page-shell-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        justify-content: flex-end;
        align-items: center;
    }
    /* Recent Runs rows */
    .tx-recent-run-row {
        border: 1px solid rgba(250, 250, 250, 0.12);
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        margin: 0 0 0.65rem 0;
        background: var(--secondary-background-color, rgba(38, 39, 48, 0.9));
        color: var(--text-color, #fafafa);
        transition: border-color 0.12s ease, background 0.12s ease;
    }
    .tx-recent-run-row:hover {
        border-color: rgba(31, 119, 180, 0.55);
        background: rgba(31, 119, 180, 0.12);
    }
    .tx-recent-run-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-color, #fafafa);
        margin: 0 0 0.15rem 0;
        line-height: 1.3;
    }
    .tx-recent-run-meta {
        font-size: 0.82rem;
        color: var(--text-color, #c9d1d9);
        opacity: 0.85;
        margin: 0 0 0.35rem 0;
    }
    .tx-recent-run-secondary {
        font-size: 0.78rem;
        color: var(--text-color, #8a9ab0);
        opacity: 0.7;
        margin: 0 0 0.45rem 0;
    }
    /* Compact tertiary action links (nav jumps + downloads) */
    [class*="st-key-tx_al_"] [data-testid="stButton"],
    [class*="st-key-tx_al_"] [data-testid="stDownloadButton"] {
        margin: 0 !important;
    }
    [class*="st-key-tx_al_"] [data-testid="stButton"] > button,
    [class*="st-key-tx_al_"] [data-testid="stDownloadButton"] > button,
    [class*="st-key-tx_al_"] > button {
        min-height: unset !important;
        height: auto !important;
        padding: 0.1rem 0.15rem !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        color: #9ec9e6 !important;
        gap: 0.28rem !important;
    }
    [class*="st-key-tx_al_"] [data-testid="stButton"] > button span[data-testid="stIconMaterial"],
    [class*="st-key-tx_al_"] [data-testid="stButton"] > button [data-testid="stIconMaterial"],
    [class*="st-key-tx_al_"] [data-testid="stDownloadButton"] > button span[data-testid="stIconMaterial"],
    [class*="st-key-tx_al_"] [data-testid="stDownloadButton"] > button [data-testid="stIconMaterial"],
    [class*="st-key-tx_al_"] > button span[data-testid="stIconMaterial"],
    [class*="st-key-tx_al_"] > button [data-testid="stIconMaterial"] {
        font-size: 0.95rem !important;
        color: inherit !important;
        opacity: 0.9;
    }
    [class*="st-key-tx_al_"] [data-testid="stButton"] > button:hover,
    [class*="st-key-tx_al_"] [data-testid="stDownloadButton"] > button:hover,
    [class*="st-key-tx_al_"] > button:hover {
        color: #c5e3f6 !important;
        text-decoration: underline;
        background: transparent !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tx_al_"]) {
        gap: 0 !important;
        justify-content: flex-start !important;
        flex-wrap: wrap;
        align-items: center;
        margin: 0.15rem 0 0.55rem 0;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tx_al_"])
        [data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: fit-content !important;
        display: flex !important;
        align-items: center;
    }
    /* Pipe separators between action-link columns (not inside buttons —
       Streamlit tertiary buttons often clip or override ::after). */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tx_al_"])
        [data-testid="stColumn"]:not(:last-child)::after {
        content: "|";
        color: rgba(250, 250, 250, 0.38);
        margin: 0 0.55rem;
        font-size: 0.88rem;
        font-weight: 400;
        line-height: 1;
        pointer-events: none;
        user-select: none;
        flex-shrink: 0;
    }
    /* Empty states */
    .tx-empty {
        border: 1px solid rgba(250, 250, 250, 0.14);
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
        margin: 0.5rem 0 1rem 0;
        background: var(--secondary-background-color, rgba(38, 39, 48, 0.85));
        color: var(--text-color, #fafafa);
    }
    .tx-empty-hero {
        margin-top: 2.75rem;
        margin-bottom: 1.25rem;
        padding: 1.45rem 1.5rem;
        border-radius: 12px;
    }
    .tx-empty-hero h4 {
        font-size: 1.18rem;
        color: var(--text-color, #fafafa);
    }
    .tx-empty-hero p {
        font-size: 0.95rem;
        line-height: 1.45;
        color: var(--text-color, #c9d1d9);
        opacity: 0.9;
    }
    .tx-empty-missing_prerequisite { border-left: 4px solid #1f77b4; }
    .tx-empty-no_results_yet { border-left: 4px solid #8a9ab0; }
    .tx-empty-filtered_to_zero { border-left: 4px solid #c9a227; }
    .tx-empty-module_unavailable { border-left: 4px solid #9b8bb8; }
    .tx-empty-error_degraded { border-left: 4px solid #c44; }
    .tx-empty h4 {
        margin: 0 0 0.35rem 0;
        font-size: 1.05rem;
        color: var(--text-color, #fafafa);
    }
    .tx-empty p {
        margin: 0 0 0.75rem 0;
        font-size: 0.9rem;
        color: var(--text-color, #c9d1d9);
        opacity: 0.85;
    }
    /* Chart gallery cards */
    .tx-chart-card {
        border: 1px solid rgba(120, 130, 145, 0.28);
        border-radius: 10px;
        padding: 0.65rem;
        margin-bottom: 0.5rem;
        min-height: 200px;
        background: rgba(255, 255, 255, 0.6);
    }
    .tx-chart-card-meta {
        font-size: 0.72rem;
        color: #7a8a9e;
        margin-bottom: 0.4rem;
        line-height: 1.35;
    }
    .tx-chart-family-shell {
        border-left: 3px solid rgba(31, 119, 180, 0.25);
        padding: 0.15rem 0 0.15rem 0.55rem;
        margin: 0.15rem 0 0.35rem 0;
    }
    .tx-chart-slice-shell {
        border-left: 2px solid rgba(120, 130, 145, 0.2);
        padding: 0.1rem 0 0.1rem 0.45rem;
        margin: 0.1rem 0 0.25rem 0;
    }
    .tx-chart-module-row {
        margin: 0.15rem 0 0.35rem 0;
    }
    .tx-charts-filter-toolbar {
        margin: 0.15rem 0 0.45rem 0;
    }
    .tx-charts-filter-toolbar div[data-testid="stHorizontalBlock"] {
        justify-content: flex-start !important;
        gap: 0.5rem !important;
    }
    /* Key-based: markdown wrappers do not parent Streamlit widgets in the DOM.
       Target the element container, button, and Streamlit's inner flex/markdown
       so labels stay left (default secondary buttons center their content). */
    [class*="st-key-charts_module_toggle_"],
    [class*="st-key-charts_module_toggle_"] [data-testid="stButton"] {
        width: 100% !important;
        text-align: left !important;
    }
    [class*="st-key-charts_module_toggle_"] [data-testid="stButton"] > button,
    [class*="st-key-charts_module_toggle_"] [data-testid="stBaseButton-secondary"],
    [class*="st-key-charts_module_toggle_"] button {
        background: transparent;
        border: 1px solid transparent;
        box-shadow: none;
        color: inherit;
        font-weight: 500;
        width: 100% !important;
        display: inline-flex !important;
        justify-content: flex-start !important;
        text-align: left !important;
    }
    /* Streamlit BaseButton nests a full-width flex row with justify-content:center. */
    [class*="st-key-charts_module_toggle_"] button div,
    [class*="st-key-charts_module_toggle_"] button [data-testid="stMarkdownContainer"],
    [class*="st-key-charts_module_toggle_"] button p,
    [class*="st-key-charts_module_toggle_"] button span {
        width: 100% !important;
        margin: 0;
        justify-content: flex-start !important;
        text-align: left !important;
    }
    [class*="st-key-charts_module_toggle_"] [data-testid="stButton"] > button:hover,
    [class*="st-key-charts_module_toggle_"] [data-testid="stBaseButton-secondary"]:hover,
    [class*="st-key-charts_module_toggle_"] button:hover {
        background: rgba(120, 130, 145, 0.08);
        border-color: rgba(120, 130, 145, 0.18);
    }
    /* Chart family / slice expanders — keep summary labels left-aligned */
    .main [data-testid="stExpander"] details summary,
    .main [data-testid="stExpander"] details summary [data-testid="stMarkdownContainer"],
    .main [data-testid="stExpander"] details summary p,
    .main [data-testid="stExpander"] details summary span {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    /* Review modules — compact rows; reveal ✕ on hover / keyboard focus */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"]) {
        gap: 0.25rem !important;
        align-items: center !important;
        margin: 0 !important;
        padding: 0.05rem 0.2rem;
        border-radius: 0.35rem;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"]):hover {
        background: rgba(120, 130, 145, 0.08);
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"])
        [data-testid="stColumn"] {
        padding: 0 !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"])
        [data-testid="stMarkdownContainer"] {
        margin: 0 !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"])
        [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        line-height: 1.35;
    }
    [class*="st-key-"][class*="_review_rm_"] [data-testid="stButton"] {
        margin: 0 !important;
    }
    [class*="st-key-"][class*="_review_rm_"] [data-testid="stButton"] > button,
    [class*="st-key-"][class*="_review_rm_"] button {
        min-height: unset !important;
        height: 1.5rem !important;
        padding: 0 0.35rem !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        opacity: 0;
        transition: opacity 0.12s ease;
        color: #c9a0a0 !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"]):hover
        [class*="_review_rm_"] button,
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="_review_rm_"]):focus-within
        [class*="_review_rm_"] button,
    [class*="st-key-"][class*="_review_rm_"] button:focus-visible {
        opacity: 1;
    }
    [class*="st-key-"][class*="_review_rm_"] [data-testid="stButton"] > button:hover,
    [class*="st-key-"][class*="_review_rm_"] button:hover {
        color: #e8b4b4 !important;
        background: rgba(180, 90, 90, 0.12) !important;
    }
    /* LLM feedback — quiet thumbs; persistent low opacity + hover/focus */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="llm_fb_"]) {
        gap: 0.2rem !important;
        align-items: center !important;
        margin: 0 !important;
    }
    [class*="st-key-"][class*="llm_fb_up_"] [data-testid="stButton"] > button,
    [class*="st-key-"][class*="llm_fb_down_"] [data-testid="stButton"] > button,
    [class*="st-key-"][class*="llm_fb_up_"] button,
    [class*="st-key-"][class*="llm_fb_down_"] button {
        min-height: unset !important;
        height: 1.55rem !important;
        padding: 0 0.3rem !important;
        font-size: 0.9rem !important;
        opacity: 0.4;
        transition: opacity 0.12s ease;
        color: #5a6570 !important;
        background: transparent !important;
        border: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="llm_fb_"]):hover
        [class*="llm_fb_"] button,
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-"][class*="llm_fb_"]):focus-within
        [class*="llm_fb_"] button,
    [class*="st-key-"][class*="llm_fb_up_"] button:focus-visible,
    [class*="st-key-"][class*="llm_fb_down_"] button:focus-visible,
    [class*="st-key-"][class*="llm_fb_up_"] button:hover,
    [class*="st-key-"][class*="llm_fb_down_"] button:hover {
        opacity: 1;
        color: #2d3740 !important;
    }
    /* Speaker chips (transcript viewer) — accent from --speaker-accent */
    span.tx-speaker-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.4rem;
        background: color-mix(
            in srgb,
            var(--speaker-accent, #5b8def) 16%,
            #f7fafc
        );
        color: var(--speaker-accent, #2c5282);
        border: 1px solid color-mix(
            in srgb,
            var(--speaker-accent, #5b8def) 35%,
            transparent
        );
    }
    span.tx-speaker-chip .tx-speaker-swatch {
        width: 0.5rem;
        height: 0.5rem;
    }
    /* Compact Turns / Segments rows */
    .tx-turn {
        margin: 0 0 0.55rem 0;
        padding: 0 0 0.45rem 0;
        border-bottom: 1px solid rgba(120, 130, 145, 0.22);
    }
    .tx-turn-header {
        margin: 0 0 0.15rem 0;
        line-height: 1.25;
        font-size: 0.92rem;
    }
    .tx-speaker-name,
    a.tx-speaker-name.tx-speaker-profile-link {
        color: var(--speaker-accent, #5b8def);
        font-weight: 650;
    }
    .tx-speaker-time {
        color: rgba(180, 190, 205, 0.92);
        font-weight: 450;
    }
    .tx-turn-body {
        margin: 0;
        padding: 0;
        line-height: 1.45;
        white-space: pre-wrap;
    }
    .tx-turn--jump {
        border-left: 3px solid rgba(31, 119, 180, 0.55);
        padding-left: 0.55rem;
        background: rgba(31, 119, 180, 0.06);
        border-radius: 0 0.35rem 0.35rem 0;
    }
    /* Collapse Streamlit markdown chrome around compact turns */
    [data-testid="stMarkdownContainer"]:has(.tx-turn) p {
        margin: 0 !important;
    }
    .tx-segment-block {
        margin: 0.15rem 0 0.35rem 0;
        padding: 0;
        border-bottom: none;
    }
    .tx-segment-block--jump {
        border-left: 3px solid rgba(31, 119, 180, 0.55);
        padding-left: 0.55rem;
        background: rgba(31, 119, 180, 0.06);
        border-radius: 0 0.35rem 0.35rem 0;
    }
    span.tx-jump-target {
        display: inline-block;
        padding: 0.1rem 0.4rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        background: rgba(31, 119, 180, 0.12);
        color: #8eb7e8;
        border: 1px solid rgba(31, 119, 180, 0.25);
    }
    /* Avoid browser scroll-anchoring jumps when the player updates in-place. */
    [data-testid="stMain"] {
        overflow-anchor: none;
    }
</style>
<script>
    // Scroll to top button functionality
    window.addEventListener('DOMContentLoaded', function() {
        // Create the button
        const btn = document.createElement('button');
        btn.id = 'scroll-to-top-btn';
        btn.innerHTML = '↑';
        btn.title = 'Return to top';
        btn.onclick = function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        };
        document.body.appendChild(btn);

        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                btn.classList.add('show');
            } else {
                btn.classList.remove('show');
            }
        });
    });

    // Keep reading position when ▶ / Play triggers a fragment redraw that
    // would otherwise scroll the newly focused audio player into view.
    (function() {
        if (window.__txPlayScrollPreserve) return;
        window.__txPlayScrollPreserve = true;
        const KEY = 'txPreserveScrollY';
        const isPlayControl = function(el) {
            const btn = el && el.closest ? el.closest('button') : null;
            if (!btn) return false;
            const text = (btn.innerText || btn.textContent || '').trim();
            return text === '▶' || text.indexOf('Play') === 0;
        };
        const restore = function() {
            const raw = sessionStorage.getItem(KEY);
            if (raw === null) return;
            const y = parseInt(raw, 10);
            if (!Number.isFinite(y)) return;
            window.scrollTo(0, y);
        };
        document.addEventListener('pointerdown', function(e) {
            if (!isPlayControl(e.target)) return;
            sessionStorage.setItem(
                KEY,
                String(window.scrollY || window.pageYOffset || 0)
            );
            let frames = 0;
            const tick = function() {
                restore();
                frames += 1;
                if (frames < 45) {
                    window.requestAnimationFrame(tick);
                } else {
                    sessionStorage.removeItem(KEY);
                }
            };
            window.requestAnimationFrame(tick);
        }, true);
    })();
</script>
""",
        unsafe_allow_html=True,
    )
