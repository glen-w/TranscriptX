"""Shared presentation helpers for LLM artifact headings and provenance badges."""

from __future__ import annotations

import re

import streamlit as st

_LEADING_MD_HEADING = re.compile(r"^#[^\n]*\n+")
_PROVENANCE_FOOTER = re.compile(
    r"\n---\s*\n(?:Prompt version:[^\n]*\n)?(?:Model:[^\n]*\n?)?\s*$",
    re.IGNORECASE,
)


def provenance_badges(provenance: dict | None) -> list[str]:
    if not isinstance(provenance, dict):
        return []
    badges: list[str] = []
    prompt_version = str(provenance.get("prompt_version") or "").strip()
    model = str(provenance.get("model") or "").strip()
    if prompt_version:
        badges.append(f"Prompt v{prompt_version}")
    if model:
        badges.append(model)
    return badges


def strip_leading_markdown_heading(markdown: str) -> str:
    return _LEADING_MD_HEADING.sub("", markdown.lstrip(), count=1).lstrip()


def strip_provenance_footer(markdown: str) -> str:
    return _PROVENANCE_FOOTER.sub("\n", markdown).rstrip() + "\n"


def render_badge_row(labels: list[str]) -> None:
    parts = "".join(f'<span class="tx-badge">{label}</span>' for label in labels if label)
    if parts:
        st.markdown(
            f'<div style="margin:0.15rem 0 0.65rem 0;">{parts}</div>',
            unsafe_allow_html=True,
        )


def render_markdown_without_heading_or_provenance(markdown: str) -> None:
    body = strip_provenance_footer(strip_leading_markdown_heading(markdown))
    if body.strip():
        st.markdown(body)
