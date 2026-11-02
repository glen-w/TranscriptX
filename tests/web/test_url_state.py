"""URL ↔ session navigation-context mirroring (refresh keeps context)."""

from __future__ import annotations

import pytest

from transcriptx.web import url_state
from transcriptx.web.state import PAGE_KEY, RUN_ID_KEY, SUBJECT_ID_KEY, SUBJECT_TYPE_KEY


@pytest.mark.unit
def test_hydrate_applies_page_subject_run_once() -> None:
    ss: dict = {PAGE_KEY: "Home"}
    qp = {
        "page": "Overview",
        "subject_type": "transcript",
        "subject_id": "slug",
        "run_id": "r1",
    }
    assert url_state.hydrate_session_from_url(ss, qp) is True
    assert ss[PAGE_KEY] == "Overview"
    assert ss[SUBJECT_TYPE_KEY] == "transcript"
    assert ss[SUBJECT_ID_KEY] == "slug"
    assert ss[RUN_ID_KEY] == "r1"
    # Second call in the same session is a no-op even if the URL changed.
    ss2 = dict(ss)
    assert url_state.hydrate_session_from_url(ss2, {"page": "Charts"}) is False
    assert ss2[PAGE_KEY] == "Overview"


@pytest.mark.unit
def test_hydrate_ignores_unknown_page_and_bad_subject() -> None:
    ss: dict = {PAGE_KEY: "Home"}
    assert (
        url_state.hydrate_session_from_url(
            ss, {"page": "Nope", "subject_type": "thing", "subject_id": "x"}
        )
        is False
    )
    assert ss[PAGE_KEY] == "Home"
    assert SUBJECT_ID_KEY not in ss


@pytest.mark.unit
def test_hydrate_migrates_legacy_page_keys() -> None:
    ss: dict = {}
    url_state.hydrate_session_from_url(ss, {"page": "Audio Prep"})
    assert ss[PAGE_KEY] == "Tools"


@pytest.mark.unit
def test_sync_writes_only_nav_keys_and_preserves_others() -> None:
    ss = {
        PAGE_KEY: "Charts",
        SUBJECT_TYPE_KEY: "transcript",
        SUBJECT_ID_KEY: "slug",
        RUN_ID_KEY: "r1",
    }
    qp: dict = {"perf_scenario": "x"}
    assert url_state.sync_url_from_session(ss, qp) is True
    assert qp == {
        "perf_scenario": "x",
        "page": "Charts",
        "subject_type": "transcript",
        "subject_id": "slug",
        "run_id": "r1",
    }
    # Unchanged context → no write.
    assert url_state.sync_url_from_session(ss, qp) is False


@pytest.mark.unit
def test_sync_clears_stale_keys_and_omits_home() -> None:
    qp = {
        "page": "Charts",
        "subject_type": "transcript",
        "subject_id": "slug",
        "run_id": "r1",
    }
    ss = {PAGE_KEY: "Home"}
    assert url_state.sync_url_from_session(ss, qp) is True
    assert qp == {}
