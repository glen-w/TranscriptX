"""
Streamlit shell: page config and global styles.

Kept separate from ``app.py`` so the entry module focuses on routing and pages.
"""

from __future__ import annotations

import streamlit as st


def configure_streamlit_page() -> None:
    """``st.set_page_config`` must run before other Streamlit commands."""
    st.set_page_config(
        page_title="TranscriptX",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_global_styles() -> None:
    """Inject shared CSS and scroll-to-top behavior."""
    st.markdown(
        """
<style>
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
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: left;
    }
    .speaker-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    /* Navigation section headers */
    .nav-section-header {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a9ab0;
        margin: 1.1rem 0 0.25rem 0.1rem;
        padding: 0;
        line-height: 1.2;
        user-select: none;
    }
    /* Style navigation buttons to look like sidebar links */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: transparent;
        border: none;
        border-radius: 6px;
        color: #3d5166;
        text-align: left;
        padding: 0.35rem 0.6rem;
        font-weight: normal;
        font-size: 0.92rem;
        box-shadow: none;
        width: 100%;
        transition: background 0.12s ease, color 0.12s ease;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        color: #1f77b4;
        background: #eef4fb;
        text-decoration: none;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:focus {
        box-shadow: none;
        outline: none;
    }
    /* Active nav item — left-bar highlight */
    div[data-testid="stButton"] > button[kind="secondary"].nav-active,
    .nav-active-item > div[data-testid="stButton"] > button[kind="secondary"] {
        background: #ddeeff;
        color: #1f77b4;
        font-weight: 600;
    }
    /* Subject panel section headers (CONTEXT / VIEWS / FILES / ADVANCED) */
    .subject-section-header {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a9ab0;
        margin: 1rem 0 0.2rem 0.1rem;
        line-height: 1.2;
        user-select: none;
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
    /* Context bar — single quiet orientation line */
    .tx-context-bar-wrap {
        position: sticky;
        top: 0;
        z-index: 50;
        margin: 0 0 0.5rem 0;
        padding: 0.2rem 0 0.35rem 0;
        background: var(--background-color, rgba(255, 255, 255, 0.92));
        backdrop-filter: blur(6px);
        border-bottom: 1px solid rgba(120, 130, 145, 0.12);
    }
    .tx-context-bar-inner {
        line-height: 1.4;
    }
    .tx-context-line {
        font-size: 0.76rem;
        font-weight: 400;
        color: #8a9ab0;
        letter-spacing: 0.01em;
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
    /* Page help expander — lighter than main content */
    .tx-page-help {
        margin-top: 1.25rem;
    }
    .tx-page-help [data-testid="stExpander"] details summary,
    .tx-page-help [data-testid="stExpander"] details summary p {
        font-size: 0.82rem !important;
        font-weight: 500;
        color: #8a9ab0 !important;
    }
    .tx-page-help [data-testid="stExpander"] .streamlit-expanderContent {
        font-size: 0.88rem;
        color: #5a6b7d;
    }
    /* Empty states */
    .tx-empty {
        border: 1px solid rgba(120, 130, 145, 0.25);
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
        margin: 0.5rem 0 1rem 0;
        background: rgba(248, 250, 252, 0.85);
    }
    .tx-empty-hero {
        margin-top: 2.75rem;
        margin-bottom: 1.25rem;
        padding: 1.45rem 1.5rem;
        border-radius: 12px;
    }
    .tx-empty-hero h4 {
        font-size: 1.18rem;
        color: #2c3e50;
    }
    .tx-empty-hero p {
        font-size: 0.95rem;
        line-height: 1.45;
    }
    .tx-empty-missing_prerequisite { border-left: 4px solid #1f77b4; }
    .tx-empty-no_results_yet { border-left: 4px solid #8a9ab0; }
    .tx-empty-filtered_to_zero { border-left: 4px solid #c9a227; }
    .tx-empty-module_unavailable { border-left: 4px solid #9b8bb8; }
    .tx-empty-error_degraded { border-left: 4px solid #c44; }
    .tx-empty h4 {
        margin: 0 0 0.35rem 0;
        font-size: 1.05rem;
        color: #2c3e50;
    }
    .tx-empty p {
        margin: 0 0 0.75rem 0;
        font-size: 0.9rem;
        color: #5a6b7d;
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
    /* Speaker chips (transcript viewer) */
    span.tx-speaker-chip {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.4rem;
        background: linear-gradient(135deg, #e8f0fe 0%, #eef4fb 100%);
        color: #2c5282;
        border: 1px solid rgba(31, 119, 180, 0.2);
    }
    .tx-segment-block {
        margin: 0.65rem 0;
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    }
    .tx-transcript-controls {
        position: sticky;
        top: 2.1rem;
        z-index: 40;
        padding: 0.35rem 0 0.65rem 0;
        margin-bottom: 0.5rem;
        background: var(--background-color, rgba(255, 255, 255, 0.94));
        border-bottom: 1px solid rgba(120, 130, 145, 0.15);
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
</script>
""",
        unsafe_allow_html=True,
    )
