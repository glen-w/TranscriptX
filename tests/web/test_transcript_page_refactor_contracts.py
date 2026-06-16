from __future__ import annotations

from contextlib import contextmanager

import transcriptx.web.page_modules.transcript as mod
from transcriptx.web.models.search import SegmentRef, TranscriptRef
from transcriptx.web.transcript_view_state import transcript_context_result


def test_navigate_to_segment_sets_canonical_state_and_reruns(monkeypatch) -> None:
    state: dict = {}
    called = {"rerun": 0}

    class _DummySt:
        session_state = state

        @staticmethod
        def rerun():
            called["rerun"] += 1

    monkeypatch.setattr(mod, "st", _DummySt)
    ref = SegmentRef(
        transcript_ref=TranscriptRef(session_slug="slug", run_id="run1"),
        primary_locator="index",
        segment_index=7,
    )

    mod.navigate_to_segment(ref, highlight_query="hello")

    assert state[mod.SUBJECT_TYPE_KEY] == "transcript"
    assert state[mod.SUBJECT_ID_KEY] == "slug"
    assert state[mod.RUN_ID_KEY] == "run1"
    assert state[mod.PAGE_KEY] == "Transcript"
    assert state[mod.NAV_REQUEST_KEY].highlight_query == "hello"
    assert called["rerun"] == 1


def test_render_transcript_controls_contract(monkeypatch) -> None:
    calls: list[str] = []
    state = {"timestamp_format": "seconds"}

    class _DummySt:
        session_state = state

        @staticmethod
        def markdown(text, unsafe_allow_html=False):
            if unsafe_allow_html:
                calls.append(text)

        @staticmethod
        def text_input(_label, key):
            assert key == "transcript_search"
            return "needle"

        @staticmethod
        def checkbox(_label, key):
            assert key == "show_timestamps"
            return True

    monkeypatch.setattr(mod, "st", _DummySt)
    result = mod._render_transcript_controls()
    assert result.search_text == "needle"
    assert result.show_timestamps is True
    assert result.format_key == "seconds"
    assert calls[0] == '<div class="tx-transcript-controls">'
    assert calls[-1] == "</div>"


def test_resolve_and_prepare_segments_only_enriches_when_non_empty(monkeypatch) -> None:
    called = {"count": 0}

    def _fake_resolve(segments, selected):
        called["count"] += 1
        assert selected == "slug/run"
        return [{"text": "resolved"}]

    monkeypatch.setattr(mod, "resolve_speaker_names_from_db", _fake_resolve)
    assert mod._resolve_and_prepare_segments({"segments": []}, "slug/run") == []
    assert called["count"] == 0
    out = mod._resolve_and_prepare_segments({"segments": [{"text": "x"}]}, "slug/run")
    assert called["count"] == 1
    assert out == [{"text": "resolved"}]


def test_render_transcript_viewer_does_not_consume_nav_request_on_empty_segments(
    monkeypatch,
) -> None:
    state = {mod.NAV_REQUEST_KEY: "keep-me"}

    class _DummySt:
        session_state = state

        @staticmethod
        @contextmanager
        def spinner(_msg):
            yield

        @staticmethod
        def error(_msg):
            return None

        @staticmethod
        def exception(_exc):
            return None

        @staticmethod
        def divider():
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_render_transcript_help", lambda _h: None)
    monkeypatch.setattr(mod, "_render_metadata_metrics", lambda _d: None)
    monkeypatch.setattr(mod, "render_download_row", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_empty_state", lambda *a, **k: None)
    monkeypatch.setattr(
        mod,
        "resolve_viewer_preflight",
        lambda *a, **k: mod.ViewerPreflight(
            status="ok",
            context_result=transcript_context_result(
                ok=True,
                session_slug="slug",
                run_id="run1",
                run_root=__import__("pathlib").Path("/tmp"),
            ),
        ),
    )
    monkeypatch.setattr(mod, "load_transcript_by_session", lambda _s: {"segments": []})
    monkeypatch.setattr(
        mod,
        "resolve_transcript_artifacts",
        lambda **_k: __import__("types").SimpleNamespace(
            txt_file=None, csv_file=None, srt_file=None, json_file=None
        ),
    )
    monkeypatch.setattr(
        mod,
        "consume_nav_request",
        lambda _s: (_ for _ in ()).throw(
            AssertionError("consume_nav_request should not be called when no segments")
        ),
    )

    mod.render_transcript_viewer()
    assert state[mod.NAV_REQUEST_KEY] == "keep-me"
