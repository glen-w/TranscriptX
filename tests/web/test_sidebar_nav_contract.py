"""Guardrails for sidebar Streamlit API usage and nav contracts."""

from __future__ import annotations

import inspect
from pathlib import Path

import streamlit as st

from transcriptx.web.navigation import PAGE_SPECS, pages_in_section
from transcriptx.web.sidebar import (
    _CANONICAL_TO_LABEL,
    _LABEL_TO_CANONICAL,
    _SUBJECT_TYPE_OPTIONS,
    _SUBJECT_TYPE_SELECTOR_KEY,
    _normalise_subject_type_selector,
)


def _sidebar_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "sidebar.py"
    ).read_text(encoding="utf-8")


def test_sidebar_does_not_use_st_expander() -> None:
    assert "st.expander" not in _sidebar_source()


def test_sidebar_does_not_use_st_toggle() -> None:
    source = _sidebar_source()
    assert "st.toggle" not in source
    assert "_sidebar_section" not in source


def test_sidebar_has_no_tx_nav_state_keys() -> None:
    source = _sidebar_source()
    assert "TX_NAV_" not in source


def test_sidebar_uses_static_nav_sections() -> None:
    source = _sidebar_source()
    assert "_nav_section" in source
    assert "pages_in_section" in source


def test_sidebar_uses_segmented_control_not_radio() -> None:
    source = _sidebar_source()
    assert "st.segmented_control" in source
    assert "st.radio" not in source
    assert _SUBJECT_TYPE_SELECTOR_KEY == "subject_type_selector"
    assert _SUBJECT_TYPE_OPTIONS == ("Transcript", "Group")
    assert _LABEL_TO_CANONICAL == {"Transcript": "transcript", "Group": "group"}


def test_sidebar_section_title_settings_is_system() -> None:
    from transcriptx.web.sidebar import _SECTION_TITLES

    assert _SECTION_TITLES["settings"] == "System"


def test_all_page_specs_remain_reachable_in_section_order() -> None:
    ordered: list[str] = []
    for section in ("primary", "workflow", "view", "tools", "settings"):
        ordered.extend(spec.key for spec in pages_in_section(section))
    # Legacy destinations stay in PAGE_SPECS but are filtered from sidebar.
    sidebar_keys = [
        spec.key for spec in PAGE_SPECS if getattr(spec, "subsection", None) != "legacy"
    ]
    assert ordered == sidebar_keys


def test_subject_type_selector_normalisation_and_mode_switch_shape() -> None:
    state: dict = {"subject_type": "group", "subject_type_selector": "bogus"}
    assert _normalise_subject_type_selector(state) == "Group"
    assert state["subject_type_selector"] == "Group"

    state2 = {"subject_type": "transcript", "subject_type_selector": "Group"}
    assert _normalise_subject_type_selector(state2) == "Group"
    assert state2["subject_type_selector"] == "Group"

    state3 = {"subject_type_selector": ["Transcript"]}
    assert _normalise_subject_type_selector(state3) == "Transcript"

    state4: dict = {}
    assert _normalise_subject_type_selector(state4) == "Transcript"
    assert state4["subject_type_selector"] == "Transcript"
    assert None not in (state4["subject_type_selector"],)


def test_canonical_mapping_round_trip() -> None:
    for label, canonical in _LABEL_TO_CANONICAL.items():
        assert _CANONICAL_TO_LABEL[canonical] == label


def test_streamlit_expander_key_support_is_version_dependent() -> None:
    """Document dynamic expander availability; sidebar avoids keyed expanders either way."""
    sig = inspect.signature(st.expander)
    has_key = "key" in sig.parameters
    has_on_change = "on_change" in sig.parameters
    assert has_key == has_on_change


def test_streamlit_exposes_segmented_control() -> None:
    assert hasattr(st, "segmented_control")
    assert "streamlit>=1.55.0" in (
        Path(__file__).resolve().parents[2] / "requirements.txt"
    ).read_text(encoding="utf-8")
