"""Direct unit tests for transcriptx.web.state session helpers."""

from __future__ import annotations

import pytest
import streamlit as st

from transcriptx.web.state import (
    ARTIFACTS_KEY_PREVIEW_ID,
    ARTIFACTS_KEY_SCOPE,
    ARTIFACTS_KEY_SELECTED_IDS,
    ARTIFACTS_KEY_SHOW_MORE,
    CHARTS_FILTER_DEFAULTS,
    CHARTS_KEY_FILTERS_INIT,
    DATA_KEY_ARTIFACT_PRESET,
    PAGE_FLASH_KIND,
    PAGE_FLASH_MESSAGE,
    RUN_ID_KEY,
    RUN_SELECTOR_KEY,
    SUBJECT_ID_KEY,
    SUBJECT_ID_SELECTOR_KEY,
    SUBJECT_TYPE_KEY,
    SUBJECT_TYPE_SELECTOR_KEY,
    apply_subject_context,
    charts_resettable_keys,
    consume_artifact_preset,
    get_current_subject_context,
    reconcile_artifact_selection,
    set_current_subject_context,
    set_page_flash,
    try_page_toast,
)


@pytest.fixture
def clear_st_session():
    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.mark.unit
def test_get_current_subject_context_reads_canonical_keys(clear_st_session) -> None:
    st.session_state[SUBJECT_TYPE_KEY] = "transcript"
    st.session_state[SUBJECT_ID_KEY] = "slug-a"
    st.session_state[RUN_ID_KEY] = "run-1"
    assert get_current_subject_context() == ("transcript", "slug-a", "run-1")


@pytest.mark.unit
def test_get_current_subject_context_rejects_unknown_subject_type(
    clear_st_session,
) -> None:
    st.session_state[SUBJECT_TYPE_KEY] = "library"
    st.session_state[SUBJECT_ID_KEY] = "x"
    st.session_state[RUN_ID_KEY] = "y"
    assert get_current_subject_context() == (None, "x", "y")


@pytest.mark.unit
def test_apply_subject_context_sets_type_label_and_clears_pickers() -> None:
    ss = {
        SUBJECT_ID_SELECTOR_KEY: "stale",
        RUN_SELECTOR_KEY: "stale-run",
        SUBJECT_TYPE_SELECTOR_KEY: "Group",
    }
    apply_subject_context(
        ss,
        subject_type="transcript",
        subject_id="slug",
        run_id="run-9",
    )
    assert ss[SUBJECT_TYPE_KEY] == "transcript"
    assert ss[SUBJECT_ID_KEY] == "slug"
    assert ss[RUN_ID_KEY] == "run-9"
    assert ss[SUBJECT_TYPE_SELECTOR_KEY] == "Transcript"
    assert SUBJECT_ID_SELECTOR_KEY not in ss
    assert RUN_SELECTOR_KEY not in ss


@pytest.mark.unit
def test_apply_subject_context_skips_type_label_when_subject_none() -> None:
    ss = {SUBJECT_TYPE_SELECTOR_KEY: "Transcript"}
    apply_subject_context(ss, subject_type=None, subject_id=None, run_id=None)
    assert ss[SUBJECT_TYPE_KEY] is None
    assert ss[SUBJECT_TYPE_SELECTOR_KEY] == "Transcript"


@pytest.mark.unit
def test_apply_subject_context_pops_locked_type_selector() -> None:
    class _Locked(dict):
        def __setitem__(self, key, value):  # noqa: ANN001
            if key == SUBJECT_TYPE_SELECTOR_KEY:
                err = type("StreamlitAPIException", (Exception,), {})(
                    "cannot be modified after the widget is instantiated"
                )
                raise err
            return super().__setitem__(key, value)

    ss = _Locked({SUBJECT_TYPE_SELECTOR_KEY: "Group"})
    apply_subject_context(ss, subject_type="transcript", subject_id="s", run_id="r")
    assert SUBJECT_TYPE_SELECTOR_KEY not in ss
    assert ss[SUBJECT_TYPE_KEY] == "transcript"


@pytest.mark.unit
def test_apply_subject_context_reraises_non_streamlit_errors() -> None:
    class _Boom(dict):
        def __setitem__(self, key, value):  # noqa: ANN001
            if key == SUBJECT_TYPE_SELECTOR_KEY:
                raise RuntimeError("other")
            return super().__setitem__(key, value)

    with pytest.raises(RuntimeError, match="other"):
        apply_subject_context(_Boom(), subject_type="group", subject_id="g", run_id="r")


@pytest.mark.unit
def test_set_current_subject_context_delegates_to_session(clear_st_session) -> None:
    set_current_subject_context(subject_type="group", subject_id="uuid", run_id="run")
    assert st.session_state[SUBJECT_TYPE_KEY] == "group"
    assert st.session_state[SUBJECT_ID_KEY] == "uuid"
    assert st.session_state[RUN_ID_KEY] == "run"
    assert st.session_state[SUBJECT_TYPE_SELECTOR_KEY] == "Group"


@pytest.mark.unit
def test_set_page_flash(clear_st_session) -> None:
    set_page_flash("warning", "Heads up")
    assert st.session_state[PAGE_FLASH_KIND] == "warning"
    assert st.session_state[PAGE_FLASH_MESSAGE] == "Heads up"


@pytest.mark.unit
def test_try_page_toast_swallows_errors(monkeypatch) -> None:
    import streamlit as streamlit_mod

    def _boom(_message: str) -> None:
        raise AttributeError("no toast")

    monkeypatch.setattr(streamlit_mod, "toast", _boom, raising=False)
    try_page_toast("noop")  # must not raise


@pytest.mark.unit
def test_reconcile_artifact_selection_clears_on_scope_change() -> None:
    ss = {
        ARTIFACTS_KEY_SCOPE: ("transcript", "a", "r1"),
        ARTIFACTS_KEY_SELECTED_IDS: ["x"],
        ARTIFACTS_KEY_PREVIEW_ID: "x",
        ARTIFACTS_KEY_SHOW_MORE: "stats",
    }
    reconcile_artifact_selection(
        ss, subject_type="transcript", subject_id="a", run_id="r2"
    )
    assert ss[ARTIFACTS_KEY_SELECTED_IDS] == []
    assert ss[ARTIFACTS_KEY_PREVIEW_ID] is None
    assert ss[ARTIFACTS_KEY_SHOW_MORE] is None
    assert ss[ARTIFACTS_KEY_SCOPE] == ("transcript", "a", "r2")


@pytest.mark.unit
def test_consume_artifact_preset_one_shot() -> None:
    ss = {DATA_KEY_ARTIFACT_PRESET: "Browse"}
    assert consume_artifact_preset(ss) == "Browse"
    assert DATA_KEY_ARTIFACT_PRESET not in ss
    assert consume_artifact_preset(ss) is None


@pytest.mark.unit
def test_charts_resettable_keys_match_filter_defaults() -> None:
    keys = charts_resettable_keys()
    assert CHARTS_KEY_FILTERS_INIT not in keys
    assert set(CHARTS_FILTER_DEFAULTS) == set(keys)
