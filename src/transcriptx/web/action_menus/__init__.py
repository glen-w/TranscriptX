"""Configurable interface action menus."""

from transcriptx.web.action_menus.catalog import (
    ACTIONS,
    OPTIONAL_ACTIONS,
    SECTION_ALLOWLISTS,
    SECTION_DEFAULTS,
)
from transcriptx.web.action_menus.context import (
    ActionContext,
    CanonicalIdentity,
    build_canonical_identity,
    capabilities_from_context,
)
from transcriptx.web.action_menus.ids import (
    ActionDisplay,
    ActionDisplaySetting,
    ActionId,
    NavStyle,
    SectionId,
    SectionMenuMode,
    StandardMenuMode,
)
from transcriptx.web.action_menus.prefs import (
    InterfaceDraft,
    InterfaceMenuPrefs,
    get_cached_runtime_prefs,
    load_interface_prefs,
    resolve_action_display,
)
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.action_menus.resolve import resolve_section_actions

__all__ = [
    "ACTIONS",
    "OPTIONAL_ACTIONS",
    "SECTION_ALLOWLISTS",
    "SECTION_DEFAULTS",
    "ActionContext",
    "ActionDisplay",
    "ActionDisplaySetting",
    "ActionId",
    "CanonicalIdentity",
    "InterfaceDraft",
    "InterfaceMenuPrefs",
    "NavStyle",
    "SectionId",
    "SectionMenuMode",
    "StandardMenuMode",
    "build_canonical_identity",
    "capabilities_from_context",
    "get_cached_runtime_prefs",
    "load_interface_prefs",
    "render_configured_actions",
    "resolve_action_display",
    "resolve_section_actions",
]
