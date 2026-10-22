"""Settings → Keywords panel for saved STT keyword-bias lists."""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.services.transcription.keyword_lists import (
    KeywordListError,
    MAX_KEYWORDS,
    delete_list,
    export_list_json,
    export_list_txt,
    import_list,
    list_lists,
    load_list,
    save_list,
)
from transcriptx.web.components.info_tooltip import widget_help

_BLANK = "—"
_SELECT_KEY = "settings_kw_select"
_ROWS_KEY = "settings_kw_rows"
_NAME_KEY = "settings_kw_save_name"


def render_keywords_panel() -> None:
    """CRUD for named keyword lists used by Granite Speech biasing."""
    st.subheader("Keyword lists")
    st.caption(
        "Reusable term lists for Granite Speech keyword biasing (acronyms, names, "
        "product terms). Default off on Transcribe Audio. Applied at decode time "
        "for the Granite mlx-audio provider only (up to "
        f"{MAX_KEYWORDS} terms). Saved under profiles "
        "`keyword_lists/` (survives data-dir wipes). Not the same as "
        "Corrections acronyms."
    )

    names = list_lists()
    options = [_BLANK] + names
    selected = st.selectbox(
        "Saved list",
        options=options,
        key=_SELECT_KEY,
        help=widget_help("Load a named list to edit, export, or delete."),
    )
    if selected != _BLANK and st.session_state.get("_settings_kw_loaded") != selected:
        try:
            terms = load_list(selected)
        except KeywordListError as exc:
            st.error(str(exc))
            terms = ()
        st.session_state[_ROWS_KEY] = list(terms) or [""]
        st.session_state[_NAME_KEY] = selected
        st.session_state["_settings_kw_loaded"] = selected

    if _ROWS_KEY not in st.session_state:
        st.session_state[_ROWS_KEY] = [""]

    rows: list[str] = st.session_state[_ROWS_KEY]
    to_remove: list[int] = []
    for i, value in enumerate(rows):
        c1, c2 = st.columns([8, 0.8])
        with c1:
            rows[i] = st.text_input(
                f"Term {i + 1}",
                value=value,
                key=f"settings_kw_term_{i}",
                label_visibility="collapsed",
                placeholder="Acronym or phrase",
            )
        with c2:
            if st.button("", key=f"settings_kw_rm_{i}", icon=ic.CLOSE):
                to_remove.append(i)
    for i in reversed(to_remove):
        rows.pop(i)
        st.rerun()
    if st.button("Add term", key="settings_kw_add", icon=ic.ADD):
        rows.append("")
        st.rerun()

    st.caption(f"{sum(1 for t in rows if str(t).strip())} terms (cap {MAX_KEYWORDS}).")
    name = st.text_input(
        "Save as",
        value=st.session_state.get(_NAME_KEY, ""),
        key=_NAME_KEY,
        help=widget_help("Profile name (not 'default')."),
    )

    c_save, c_del, c_json, c_txt = st.columns(4)
    with c_save:
        if st.button("Save list", type="primary", key="settings_kw_save", icon=ic.SAVE):
            terms = [str(t).strip() for t in rows if str(t).strip()]
            if not (name or "").strip():
                st.error("Enter a list name.")
            elif save_list(name.strip(), terms):
                st.session_state[_SELECT_KEY] = name.strip()
                st.session_state["_settings_kw_loaded"] = name.strip()
                st.success(f"Saved “{name.strip()}” ({len(terms)} terms).")
                st.rerun()
            else:
                st.error("Could not save list (name 'default' is reserved).")
    with c_del:
        if st.button("Delete list", key="settings_kw_delete", icon=ic.DELETE):
            target = (selected if selected != _BLANK else name).strip()
            if not target:
                st.error("Select a list to delete.")
            elif delete_list(target):
                st.session_state[_SELECT_KEY] = _BLANK
                st.session_state[_ROWS_KEY] = [""]
                st.session_state[_NAME_KEY] = ""
                st.session_state["_settings_kw_loaded"] = None
                st.success(f"Deleted “{target}”.")
                st.rerun()
            else:
                st.error(f"Could not delete “{target}”.")
    with c_json:
        if selected != _BLANK:
            try:
                payload = export_list_json(selected)
            except KeywordListError:
                payload = ""
            if payload:
                st.download_button(
                    "Download JSON",
                    data=payload,
                    file_name=f"{selected}.json",
                    mime="application/json",
                    key="settings_kw_dl_json",
                    icon=ic.DOWNLOAD,
                )
    with c_txt:
        if selected != _BLANK:
            try:
                payload = export_list_txt(selected)
            except KeywordListError:
                payload = ""
            if payload:
                st.download_button(
                    "Download TXT",
                    data=payload,
                    file_name=f"{selected}.txt",
                    mime="text/plain",
                    key="settings_kw_dl_txt",
                    icon=ic.DOWNLOAD,
                )

    uploaded = st.file_uploader(
        "Import JSON or TXT",
        type=["json", "txt"],
        key="settings_kw_upload",
        help=widget_help(
            "JSON object with keywords, JSON array, or one term per line."
        ),
    )
    import_name = st.text_input(
        "Import as name",
        value="",
        key="settings_kw_import_name",
    )
    if st.button("Import list", key="settings_kw_import", icon=ic.UPLOAD):
        if uploaded is None:
            st.error("Choose a file.")
            return
        as_name = (import_name or "").strip() or (uploaded.name.rsplit(".", 1)[0])
        try:
            text = uploaded.getvalue().decode("utf-8")
            terms = import_list(as_name, text)
        except (KeywordListError, UnicodeDecodeError) as exc:
            st.error(str(exc))
            return
        st.session_state[_SELECT_KEY] = as_name
        st.session_state[_ROWS_KEY] = list(terms) or [""]
        st.session_state[_NAME_KEY] = as_name
        st.session_state["_settings_kw_loaded"] = as_name
        st.success(f"Imported “{as_name}” ({len(terms)} terms).")
        st.rerun()
