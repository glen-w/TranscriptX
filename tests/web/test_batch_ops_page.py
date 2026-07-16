"""Tests for Batch Operations page post-run list."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from tests.web.streamlit_doubles import DummyHomeStreamlit


def test_batch_ops_renders_processed_runs_with_action_links(monkeypatch) -> None:
    import transcriptx.web.components.action_links as action_links
    import transcriptx.web.components.recent_run_row as recent_run_row
    import transcriptx.web.page_modules.batch_ops as mod

    DummyHomeStreamlit.session_state = {}
    markdown_blobs: list[str] = []
    action_keys: list[str] = []

    class _BatchStreamlit(DummyHomeStreamlit):
        @staticmethod
        def markdown(body, **_kwargs):
            markdown_blobs.append(str(body))

        @staticmethod
        def button(*_args, key=None, **_kwargs):
            if isinstance(key, str):
                action_keys.append(key)
            return False

        @staticmethod
        def success(*_args, **_kwargs):
            return None

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

    monkeypatch.setattr(mod, "st", _BatchStreamlit)
    monkeypatch.setattr(action_links, "st", _BatchStreamlit)
    monkeypatch.setattr(recent_run_row, "st", _BatchStreamlit)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {"slug-a": "Alice"})

    run = SimpleNamespace(
        created_at=datetime(2026, 7, 13, 3, 29),
        run_id="20260713_032900_abcdef12",
        run_dir=Path("/tmp/slug-a/20260713_032900_abcdef12"),
        transcript_path=Path("/tmp/alice.json"),
        selected_modules=["overview"],
        status="completed",
        duration_seconds=12.0,
        profile_name="balanced",
    )
    DummyHomeStreamlit.session_state[mod._BATCH_RESULT_KEY] = SimpleNamespace(
        success=True,
        transcript_count=1,
        errors=[],
        message="Processed 1 transcript(s), 1 succeeded",
        runs=[run],
    )

    transcript = SimpleNamespace(path=Path("/tmp/alice.json"), base_name="alice")
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: [transcript])
    monkeypatch.setattr(
        mod, "cached_get_transcript_summaries_for_paths", lambda *_a, **_k: []
    )
    monkeypatch.setattr(mod, "cached_get_module_info_list", lambda: [])
    monkeypatch.setattr(mod, "BatchController", lambda: SimpleNamespace())

    mod.render_batch_ops_page()

    joined = "\n".join(markdown_blobs)
    assert "Processed runs" in joined
    assert "Alice" in joined
    assert any("batch_run_ov_" in k for k in action_keys)
    assert any("batch_run_ch_" in k for k in action_keys)
    assert any("batch_run_dt_" in k for k in action_keys)
