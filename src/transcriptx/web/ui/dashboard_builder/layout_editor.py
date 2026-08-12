"""Selection + ↑↓ reorder editor for layout profiles (Overview / Insights)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from transcriptx.web.blocks.registry import get_block, list_blocks, list_blocks_by_group
from transcriptx.web.layouts.specs import (
    BlockPlacementModel,
    LayoutPageSpec,
    LayoutSpec,
)
from transcriptx.web.layouts.store import (
    LayoutProfileStore,
    LayoutValidationError,
    slugify_layout_id,
)

EDITABLE_PAGES = ("overview", "insights")
_INSIGHTS_SECTION_ORDER = ("summary", "speakers", "actions", "highlights")
_EDIT_STATE_KEY = "dashboard_builder_edit_pages"
_EDIT_LAYOUT_KEY = "dashboard_builder_edit_layout_id"


@dataclass
class EditedPlacement:
    placement_id: str
    block_id: str
    visible: bool = True
    section: str | None = None
    title_override: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_model(self) -> BlockPlacementModel:
        return BlockPlacementModel(
            placement_id=self.placement_id,
            block_id=self.block_id,
            title_override=self.title_override,
            visible=self.visible,
            params=dict(self.params),
            section=self.section,
        )


def layout_to_edited_pages(layout: LayoutSpec) -> dict[str, list[EditedPlacement]]:
    pages: dict[str, list[EditedPlacement]] = {}
    for page_id in EDITABLE_PAGES:
        page = layout.pages.get(page_id)
        rows: list[EditedPlacement] = []
        if page is not None:
            for block in page.blocks:
                rows.append(
                    EditedPlacement(
                        placement_id=block.placement_id,
                        block_id=block.block_id,
                        visible=block.visible,
                        section=block.section,
                        title_override=block.title_override,
                        params=dict(block.params),
                    )
                )
        pages[page_id] = rows
    return pages


def apply_page_placements(
    layout: LayoutSpec,
    edited_pages: dict[str, list[EditedPlacement]],
) -> LayoutSpec:
    """Return a copy of layout with overview/insights blocks replaced from editor state."""
    pages = {k: v.model_copy(deep=True) for k, v in layout.pages.items()}
    for page_id in EDITABLE_PAGES:
        rows = edited_pages.get(page_id, [])
        pages[page_id] = LayoutPageSpec(
            page_id=page_id,
            blocks=[row.to_model() for row in rows],
        )
    return layout.model_copy(update={"pages": pages})


def new_placement_id(page_id: str, block_id: str, existing: list[EditedPlacement]) -> str:
    base = f"{page_id}_{block_id}"
    taken = {row.placement_id for row in existing}
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def suggest_blocks_for_page(page_id: str) -> list[Any]:
    """Blocks suggested for the page (by registry group); falls back to all blocks."""
    preferred_group = {
        "overview": "Overview",
        "insights": "Insights",
    }.get(page_id)
    grouped = list_blocks_by_group()
    if preferred_group and preferred_group in grouped:
        return list(grouped[preferred_group])
    return list(list_blocks())


def placements_for_view(
    rows: list[EditedPlacement],
    *,
    page_id: str,
    section: str | None,
) -> list[tuple[int, EditedPlacement]]:
    """Return (global_index, row) pairs visible in the current editor view."""
    out: list[tuple[int, EditedPlacement]] = []
    for idx, row in enumerate(rows):
        if page_id == "insights":
            row_section = row.section or "summary"
            if section is not None and row_section != section:
                continue
        out.append((idx, row))
    return out


def move_placement(rows: list[EditedPlacement], index: int, delta: int) -> list[EditedPlacement]:
    """Move a placement within the full page list by delta (-1 / +1)."""
    if not rows or index < 0 or index >= len(rows):
        return list(rows)
    target = index + delta
    if target < 0 or target >= len(rows):
        return list(rows)
    updated = list(rows)
    updated[index], updated[target] = updated[target], updated[index]
    return updated


def move_placement_in_view(
    rows: list[EditedPlacement],
    *,
    page_id: str,
    section: str | None,
    view_index: int,
    delta: int,
) -> list[EditedPlacement]:
    """Reorder within the filtered view while preserving other sections' relative order."""
    view = placements_for_view(rows, page_id=page_id, section=section)
    if view_index < 0 or view_index >= len(view):
        return list(rows)
    neighbor = view_index + delta
    if neighbor < 0 or neighbor >= len(view):
        return list(rows)
    global_a = view[view_index][0]
    global_b = view[neighbor][0]
    updated = list(rows)
    updated[global_a], updated[global_b] = updated[global_b], updated[global_a]
    return updated


def _ensure_edit_state(layout: LayoutSpec) -> dict[str, list[EditedPlacement]]:
    layout_id = layout.id
    if (
        st.session_state.get(_EDIT_LAYOUT_KEY) != layout_id
        or _EDIT_STATE_KEY not in st.session_state
    ):
        st.session_state[_EDIT_LAYOUT_KEY] = layout_id
        st.session_state[_EDIT_STATE_KEY] = layout_to_edited_pages(layout)
    return st.session_state[_EDIT_STATE_KEY]


def _block_label(block_id: str) -> str:
    spec = get_block(block_id)
    if spec is None:
        return block_id
    return f"{spec.title} (`{block_id}`)"


def render_layout_editor(layout_id: str) -> None:
    """Streamlit Edit mode for Overview / Insights placements."""
    try:
        layout = LayoutProfileStore.load_layout(layout_id)
        builtin = LayoutProfileStore.is_builtin(layout_id)
    except (LayoutValidationError, FileNotFoundError) as exc:
        st.error(str(exc))
        return

    st.caption(
        "Layouts choose which panels appear on **Overview** and **Insights** (and their order). "
        "They do **not** choose Charts overview charts — use **Settings → Configuration → Charts overview**."
    )

    if builtin:
        st.info(
            "Built-in layouts are read-only here. Use **Save as custom layout** below to clone, "
            "then edit the custom copy."
        )

    edited = _ensure_edit_state(layout)
    page_id = st.selectbox(
        "Page",
        options=list(EDITABLE_PAGES),
        format_func=lambda p: p.title(),
        key="dashboard_builder_edit_page",
        help="Choose which layout page (Overview or Insights) to edit.",
    )
    section: str | None = None
    if page_id == "insights":
        section = st.radio(
            "Insights section",
            options=list(_INSIGHTS_SECTION_ORDER),
            horizontal=True,
            key="dashboard_builder_edit_section",
            help="Insights placements are grouped into these section buckets.",
        )

    rows = list(edited.get(page_id, []))
    view = placements_for_view(rows, page_id=page_id, section=section)

    st.subheader("Current blocks")
    if not view:
        st.caption("No blocks in this view yet. Add one below.")
    for view_ix, (global_ix, row) in enumerate(view):
        cols = st.columns([5, 1, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**{_block_label(row.block_id)}**")
            st.caption(f"placement: `{row.placement_id}`")
        with cols[1]:
            visible = st.checkbox(
                "Show",
                value=row.visible,
                key=f"dashboard_builder_vis_{layout_id}_{row.placement_id}",
                disabled=builtin,
                help="Hide without removing the placement from the layout.",
            )
            if not builtin and visible != row.visible:
                rows[global_ix] = EditedPlacement(
                    placement_id=row.placement_id,
                    block_id=row.block_id,
                    visible=visible,
                    section=row.section,
                    title_override=row.title_override,
                    params=dict(row.params),
                )
                edited[page_id] = rows
                st.session_state[_EDIT_STATE_KEY] = edited
                st.rerun()
        with cols[2]:
            if st.button(
                "↑",
                key=f"dashboard_builder_up_{layout_id}_{row.placement_id}",
                disabled=builtin or view_ix == 0,
            ):
                edited[page_id] = move_placement_in_view(
                    rows,
                    page_id=page_id,
                    section=section,
                    view_index=view_ix,
                    delta=-1,
                )
                st.session_state[_EDIT_STATE_KEY] = edited
                st.rerun()
        with cols[3]:
            if st.button(
                "↓",
                key=f"dashboard_builder_down_{layout_id}_{row.placement_id}",
                disabled=builtin or view_ix >= len(view) - 1,
            ):
                edited[page_id] = move_placement_in_view(
                    rows,
                    page_id=page_id,
                    section=section,
                    view_index=view_ix,
                    delta=1,
                )
                st.session_state[_EDIT_STATE_KEY] = edited
                st.rerun()
        with cols[4]:
            if st.button(
                "Remove",
                key=f"dashboard_builder_rm_{layout_id}_{row.placement_id}",
                disabled=builtin,
            ):
                del rows[global_ix]
                edited[page_id] = rows
                st.session_state[_EDIT_STATE_KEY] = edited
                st.rerun()

    st.subheader("Add blocks")
    suggested = suggest_blocks_for_page(page_id)
    options = {f"{spec.title} (`{spec.id}`)": spec.id for spec in suggested}
    # Also allow other groups via expander
    other_specs = [s for s in list_blocks() if s.id not in {spec.id for spec in suggested}]
    pick = st.multiselect(
        "Suggested blocks",
        options=list(options.keys()),
        default=[],
        key=f"dashboard_builder_add_{page_id}_{section or 'all'}",
        disabled=builtin,
        help="Recommended blocks for this page/section.",
    )
    if other_specs:
        with st.expander("All other blocks", expanded=False):
            other_opts = {f"{spec.title} (`{spec.id}`) [{spec.group}]": spec.id for spec in other_specs}
            more = st.multiselect(
                "Other blocks",
                options=list(other_opts.keys()),
                default=[],
                key=f"dashboard_builder_add_other_{page_id}_{section or 'all'}",
                disabled=builtin,
                help="Additional registered blocks that can be placed here.",
            )
            for label in more:
                options[label] = other_opts[label]
            pick = list(dict.fromkeys([*pick, *more]))

    if st.button(
        "Add selected blocks",
        key="dashboard_builder_add_btn",
        disabled=builtin or not pick,
    ):
        for label in pick:
            block_id = options[label]
            pid = new_placement_id(page_id, block_id, rows)
            rows.append(
                EditedPlacement(
                    placement_id=pid,
                    block_id=block_id,
                    visible=True,
                    section=section if page_id == "insights" else None,
                )
            )
        edited[page_id] = rows
        st.session_state[_EDIT_STATE_KEY] = edited
        st.rerun()

    st.divider()
    if builtin:
        st.subheader("Save as custom layout")
        new_id = st.text_input(
            "New layout id",
            value=f"{layout_id}_custom",
            key="dashboard_builder_edit_save_as_id",
            help="Slug for the custom layout file (letters, digits, underscores).",
        )
        new_title = st.text_input(
            "Title",
            value=f"{layout.title} (custom)",
            key="dashboard_builder_edit_save_as_title",
        )
        exists = False
        try:
            preview_slug = slugify_layout_id(new_id) if (new_id or "").strip() else ""
            exists = bool(
                preview_slug
                and not LayoutProfileStore.is_builtin(preview_slug)
                and LayoutProfileStore.custom_layout_exists(preview_slug)
            )
        except LayoutValidationError:
            preview_slug = ""
        overwrite_ok = True
        if exists:
            overwrite_ok = st.checkbox(
                f"Overwrite existing custom layout `{preview_slug}`",
                value=False,
                key="dashboard_builder_edit_overwrite_confirm",
            )
        if st.button("Save as custom layout", key="dashboard_builder_edit_save_as_btn"):
            try:
                slug = slugify_layout_id(new_id or "")
                if LayoutProfileStore.custom_layout_exists(slug) and not overwrite_ok:
                    st.error(
                        f"Custom layout '{slug}' already exists. "
                        "Confirm overwrite to replace it."
                    )
                else:
                    updated = apply_page_placements(layout, edited)
                    path = LayoutProfileStore.save_as_custom(
                        updated,
                        slug,
                        title=new_title or slug,
                        overwrite=True,
                    )
                    from transcriptx.web.blocks.session_context import set_active_layout_id

                    set_active_layout_id(slug)
                    st.session_state.pop(_EDIT_STATE_KEY, None)
                    st.session_state.pop(_EDIT_LAYOUT_KEY, None)
                    st.success(f"Saved custom layout to {path}")
                    st.rerun()
            except LayoutValidationError as exc:
                st.error(str(exc))
        return

    st.subheader("Save layout")
    if st.button("Save layout", key="dashboard_builder_save_layout_btn"):
        try:
            updated = apply_page_placements(layout, edited)
            # Keep charts / other pages from original layout; validate full spec.
            path = LayoutProfileStore.save_layout(updated, overwrite=True)
            st.session_state.pop(_EDIT_STATE_KEY, None)
            st.session_state.pop(_EDIT_LAYOUT_KEY, None)
            st.success(f"Saved layout to {path}")
            st.rerun()
        except LayoutValidationError as exc:
            st.error(str(exc))

    st.subheader("Delete custom layout")
    confirm_delete = st.checkbox(
        f"Confirm delete `{layout_id}`",
        value=False,
        key="dashboard_builder_edit_delete_confirm",
    )
    if st.button(
        "Delete custom layout",
        key="dashboard_builder_edit_delete_btn",
        disabled=not confirm_delete,
    ):
        try:
            path = LayoutProfileStore.delete_custom(layout_id)
            from transcriptx.web.blocks.session_context import (
                active_layout_id,
                set_active_layout_id,
            )

            if active_layout_id() == layout_id:
                set_active_layout_id("default")
            st.session_state.pop(_EDIT_STATE_KEY, None)
            st.session_state.pop(_EDIT_LAYOUT_KEY, None)
            st.success(f"Deleted custom layout {path}")
            st.rerun()
        except (LayoutValidationError, FileNotFoundError) as exc:
            st.error(str(exc))
