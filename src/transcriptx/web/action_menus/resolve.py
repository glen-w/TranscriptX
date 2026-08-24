"""Resolve configured action IDs for a section + context."""

from __future__ import annotations

from transcriptx.web.action_menus.catalog import (
    BUILT_IN_STANDARD_MENU,
    SECTION_ALLOWLISTS,
    section_default_actions,
)
from transcriptx.web.action_menus.context import (
    ActionContext,
    capabilities_from_context,
)
from transcriptx.web.action_menus.ids import ActionId, SectionId
from transcriptx.web.action_menus.prefs import (
    InterfaceMenuPrefs,
    get_cached_runtime_prefs,
)


def _standard_menu_ids(prefs: InterfaceMenuPrefs) -> list[ActionId]:
    if prefs.standard_menu_mode == "built_in":
        return list(BUILT_IN_STANDARD_MENU)
    return list(prefs.standard_menu)


def configured_actions_for_section(
    prefs: InterfaceMenuPrefs,
    section: SectionId,
    *,
    subject_type: str,
    has_run: bool,
    apply_capabilities: bool = False,
    ctx: ActionContext | None = None,
) -> list[ActionId]:
    """Return configured action IDs, optionally capability-filtered."""
    section_prefs = prefs.sections.get(section)
    if section_prefs is None or not section_prefs.show_menu:
        return []

    if section_prefs.mode == "manual":
        candidates = list(section_prefs.selected)
    elif section_prefs.mode == "use_standard":
        candidates = _standard_menu_ids(prefs)
    else:
        candidates = list(
            section_default_actions(section, subject_type=subject_type, has_run=has_run)
        )

    allow = set(SECTION_ALLOWLISTS[section])
    # Preserve candidate order (section defaults / manual / standard list order).
    seen: set[ActionId] = set()
    deduped: list[ActionId] = []
    for a in candidates:
        if a in allow and a not in seen:
            seen.add(a)
            deduped.append(a)

    if not apply_capabilities:
        return deduped
    if ctx is None:
        return deduped

    from transcriptx.web.action_menus.handlers import is_action_available

    caps = capabilities_from_context(ctx)
    return [a for a in deduped if is_action_available(a, ctx, caps)]


def resolve_section_actions(
    section: SectionId,
    ctx: ActionContext,
    *,
    prefs: InterfaceMenuPrefs | None = None,
) -> list[ActionId]:
    """Full runtime resolve for a strip."""
    prefs = prefs or get_cached_runtime_prefs()
    caps = capabilities_from_context(ctx)
    return configured_actions_for_section(
        prefs,
        section,
        subject_type=ctx.identity.subject_type,
        has_run=caps.has_valid_run,
        apply_capabilities=True,
        ctx=ctx,
    )


def overflow_actions_for_section(
    section: SectionId,
    ctx: ActionContext,
    primary: list[ActionId],
    *,
    exclude: frozenset[ActionId] | None = None,
) -> list[ActionId]:
    """Allowlisted actions not on the primary strip, filtered by capability."""
    from transcriptx.web.action_menus.handlers import is_action_available

    caps = capabilities_from_context(ctx)
    skip = set(primary)
    if exclude:
        skip.update(exclude)
    return [
        action
        for action in SECTION_ALLOWLISTS[section]
        if action not in skip and is_action_available(action, ctx, caps)
    ]
