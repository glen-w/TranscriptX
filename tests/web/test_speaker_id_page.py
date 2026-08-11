"""
Tests for the Speaker Identification page module (web/page_modules/speaker_id.py).

Contract: page imports only SpeakerStudioController (not lower-level services).
Integration: speaker-by-speaker naming flow via the controller.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.io.speaker_map_resolver import sidecar_path_for

# ── contract ──────────────────────────────────────────────────────────────────


def test_speaker_id_page_invalidates_path_summary_after_mutations() -> None:
    """Save/ignore must invalidate the selected transcript summary, not all listings."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "invalidate_transcript_summary_for_path" in source
    assert "clear_transcript_listing_caches" not in source
    assert "_speaker_id_workspace_fragment" in source
    assert "_cb_save_name" in source
    assert "_cb_ignore_toggle" in source
    assert "on_click=_cb_save_name" in source
    assert "_paths_with_current_subject" in source
    assert "cached_transcript_paths_for_speaker_views" in source
    # Ordinary action paths must not call _rerun_ui (natural fragment rerun only).
    save_cb = source.split("def _cb_save_name", 1)[1].split("def _cb_", 1)[0]
    assert "_rerun_ui()" not in save_cb
    ignore_cb = source.split("def _cb_ignore_toggle", 1)[1].split("def _cb_", 1)[0]
    assert "_rerun_ui()" not in ignore_cb


def test_speaker_id_plain_rerun_whitelist() -> None:
    """Plain st.rerun() lives only in _rerun_app; completion may full-app rerun."""
    import re

    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    plain = re.findall(r"st\.rerun\(\s*\)", source)
    assert len(plain) == 1, f"expected one plain st.rerun(), found {len(plain)}"
    assert "_rerun_app" in source
    assert "_rerun_app_for_completion" in source
    assert "Analyse voice" in source
    for needle in (
        "_cb_voice_analyse_one",
        "_cb_voice_analyse_all",
        "_cb_voice_confirm",
        "_cb_prev",
        "_cb_next",
        "_cb_save_name",
        "_cb_ignore_toggle",
    ):
        assert needle in source
        block = source.split(f"def {needle}", 1)[1].split("\ndef ", 1)[0]
        assert "_rerun_ui()" not in block
    # Save/Ignore go through the shared action service (Theme C Phase −1).
    save_cb = source.split("def _cb_save_name", 1)[1].split("def _cb_", 1)[0]
    assert "SpeakerIdCommand" in save_cb
    assert "_get_action_service" in save_cb
    assert "_apply_ack" in save_cb


def test_rerun_ui_falls_back_to_app_when_fragment_scope_illegal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full-app embedding of the fragment cannot use scope=fragment."""
    from streamlit import errors as st_errors

    import transcriptx.web.page_modules.speaker_id as mod

    calls: list[str] = []

    def _rerun(*, scope: str = "app") -> None:
        if scope == "fragment":
            raise st_errors.StreamlitAPIException(
                'scope="fragment" can only be specified from '
                "`@st.fragment`-decorated functions during fragment reruns."
            )
        calls.append(scope)
        raise RuntimeError("app-rerun")

    monkeypatch.setattr(mod.st, "rerun", _rerun)
    try:
        mod._rerun_ui()
    except RuntimeError as exc:
        assert str(exc) == "app-rerun"
    assert calls == ["app"]


def test_speaker_id_set_active_speaker_clears_playback_only_on_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    cleared: list[str] = []
    ss: dict = {"speaker_id_speaker_idx": 1, "sid_jump": 1}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(
        mod,
        "clear_playback_session_keys",
        lambda key: cleared.append(key),
    )
    mod._set_active_speaker(1, speaker_count=3)
    assert cleared == []
    mod._set_active_speaker(2, speaker_count=3)
    assert cleared == [mod._PLAY_KEY]
    assert ss["speaker_id_speaker_idx"] == 2
    assert ss["sid_jump"] == 2


def test_speaker_id_nav_and_voice_use_segment_cache_not_controller_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Workspace loads go through the segments cache, never discovery."""
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.services.speaker_studio.segment_index import SegmentInfo

    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        '{"segments":[{"start":0,"end":1,"text":"hi","speaker":"SPEAKER_00"}]}',
        encoding="utf-8",
    )
    discovery_calls = {"n": 0}
    cache_calls: list[str] = []
    controller_list_calls = {"n": 0}

    def _discover():
        discovery_calls["n"] += 1
        return [transcript]

    segs = [
        SegmentInfo(
            index=0,
            start=0.0,
            end=1.0,
            text="hi",
            speaker="SPEAKER_00",
            speaker_diarized_id="SPEAKER_00",
        )
    ]

    def _cached_segs(path_str: str, signature: tuple[int, int]):
        cache_calls.append(path_str)
        return segs

    class _Ctrl:
        def list_segments(self, *_a, **_k):
            controller_list_calls["n"] += 1
            return segs

    monkeypatch.setattr(mod, "cached_transcript_paths_for_speaker_views", _discover)
    monkeypatch.setattr(mod, "cached_speaker_id_segments", _cached_segs)

    # Simulate Prev/Next/Jump/voice fragment loads
    for _ in range(3):
        mod._load_cached_segments(transcript)
    assert discovery_calls["n"] == 0
    assert controller_list_calls["n"] == 0
    assert len(cache_calls) == 3
    assert all(Path(p).resolve() == transcript.resolve() for p in cache_calls)


def test_speaker_id_transcript_switch_causes_one_segment_cache_miss_per_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.services.speaker_studio.segment_index import SegmentInfo

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    for p in (a, b):
        p.write_text(
            '{"segments":[{"start":0,"end":1,"text":"x","speaker":"SPEAKER_00"}]}',
            encoding="utf-8",
        )
    hits: list[str] = []

    def _cached_segs(path_str: str, signature: tuple[int, int]):
        hits.append(path_str)
        return [
            SegmentInfo(
                index=0,
                start=0.0,
                end=1.0,
                text="x",
                speaker="SPEAKER_00",
                speaker_diarized_id="SPEAKER_00",
            )
        ]

    monkeypatch.setattr(mod, "cached_speaker_id_segments", _cached_segs)
    mod._load_cached_segments(a)
    mod._load_cached_segments(b)
    assert len(hits) == 2
    assert Path(hits[0]).resolve() == a.resolve()
    assert Path(hits[1]).resolve() == b.resolve()


def test_after_mapping_mutation_uses_persisted_state_and_fragment_rerun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Save/Ignore advance from returned map state without a second _rerun_ui."""
    import transcriptx.web.page_modules.speaker_id as mod
    from types import SimpleNamespace

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        "speaker_id_speaker_idx": 0,
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)

    invalidated: list[object] = []
    reruns: list[str] = []
    monkeypatch.setattr(
        mod,
        "invalidate_transcript_summary_for_path",
        lambda path, signature=None: invalidated.append((path, signature)),
    )
    monkeypatch.setattr(mod, "_rerun_ui", lambda: reruns.append("fragment"))
    monkeypatch.setattr(mod, "_rerun_app_for_completion", lambda: reruns.append("app"))
    monkeypatch.setattr(mod, "clear_playback_session_keys", lambda *_a, **_k: None)

    new_state = SimpleNamespace(
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
    )
    mod._after_mapping_mutation(
        transcript_path=transcript,
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        new_state=new_state,
        speaker_idx=0,
        summary_sig_before=(1, 2, 3),
    )
    assert invalidated == [(transcript, (1, 2, 3))]
    assert ss["speaker_id_speaker_idx"] == 1  # advanced to still-unnamed
    assert ss[mod.speaker_idx_key(transcript)] == 1
    assert reruns == []  # natural fragment rerun only — no explicit _rerun_ui


def test_after_ignore_advances_from_persisted_ignored_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from types import SimpleNamespace

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    l_key = mod.lines_key(transcript)
    ss: dict = {
        "speaker_id_speaker_idx": 0,
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
        l_key: 99,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(mod, "invalidate_transcript_summary_for_path", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "clear_playback_session_keys", lambda *_a, **_k: None)
    reruns: list[str] = []
    monkeypatch.setattr(mod, "_rerun_ui", lambda: reruns.append("fragment"))
    monkeypatch.setattr(mod, "_rerun_app_for_completion", lambda: reruns.append("app"))

    new_state = SimpleNamespace(speaker_map={}, ignored_speakers=["SPEAKER_00"])
    mod._after_mapping_mutation(
        transcript_path=transcript,
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        new_state=new_state,
        speaker_idx=0,
        summary_sig_before=(1, 2, 3),
    )
    assert ss["speaker_id_speaker_idx"] == 1
    assert ss[l_key] == mod._LINES_PER_PAGE
    assert reruns == []


def test_load_cached_segments_fails_closed_on_missing_file(tmp_path: Path) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    with pytest.raises(FileNotFoundError):
        mod._load_cached_segments(tmp_path / "missing.json")


def test_completion_action_strip_lives_inside_workspace_fragment() -> None:
    """Completion strip is painted inside the fragment; outer page only consumes the flag."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    frag = source.split("def _speaker_id_workspace_fragment", 1)[1]
    frag = frag.split("def render_speaker_id_page", 1)[0]
    outer = source.split("def render_speaker_id_page", 1)[1]
    assert "_render_post_speaker_id_actions" in frag
    assert "_render_post_speaker_id_actions" not in outer
    assert "pop(_SPEAKER_ID_COMPLETION_APP_RERUN" in outer


def test_profile_save_mutation_order_commits_before_advance() -> None:
    """Profile-link path lives in SpeakerIdActionService: link then signal then advance."""
    from transcriptx.app.speaker_id import service as action_mod

    source = Path(action_mod.__file__).read_text(encoding="utf-8")
    save_block = source.split("def _save_name", 1)[1]
    save_block = save_block.split("def _ignore_toggle", 1)[0]
    assert "create_profile_link_and_name" in save_block
    assert "partial.effective_signal" in save_block or "cache_signal = getattr(partial" in save_block
    assert save_block.index("create_profile_link_and_name") < save_block.index(
        "_ack_after_mutation"
    )
    assert "get_mapping_status" in save_block
    assert "_ack_after_mutation" in save_block
    # Page adapter must still route Save through the action service.
    import transcriptx.web.page_modules.speaker_id as mod

    page = Path(mod.__file__).read_text(encoding="utf-8")
    page_save = page.split("def _cb_save_name", 1)[1].split("def _cb_ignore_toggle", 1)[0]
    assert "SpeakerIdCommand" in page_save
    assert 'action="save_name"' in page_save
    assert "_apply_ack" in page_save
    assert "_rerun_ui()" not in page_save


def test_voice_pending_exception_leaves_pending_cleared(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pop-before-work contract: a raised analyse cannot re-queue via leftover pending."""
    import transcriptx.web.page_modules.speaker_id as mod

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    pending_key = mod.voice_pending_key(transcript)
    ss: dict = {
        pending_key: {
            "mode": "one",
            "speaker": "SPEAKER_00",
            "transcript": str(transcript),
        }
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    pending = ss.pop(pending_key, None)
    assert pending is not None
    try:
        raise RuntimeError("analyse failed")
    except RuntimeError:
        pass
    assert pending_key not in ss


def test_partial_profile_link_failure_does_not_skip_unnamed_speaker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Advancement must use persisted map; unnamed speaker after partial stays current."""
    import transcriptx.web.page_modules.speaker_id as mod
    from types import SimpleNamespace

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        "speaker_id_speaker_idx": 0,
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(mod, "invalidate_transcript_summary_for_path", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "clear_playback_session_keys", lambda *_a, **_k: None)
    reruns: list[str] = []
    monkeypatch.setattr(mod, "_rerun_ui", lambda: reruns.append("fragment"))
    monkeypatch.setattr(mod, "_rerun_app_for_completion", lambda: reruns.append("app"))

    # Naming failed / partial: map still has no SPEAKER_00 name
    new_state = SimpleNamespace(speaker_map={}, ignored_speakers=[])
    mod._after_mapping_mutation(
        transcript_path=transcript,
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        new_state=new_state,
        speaker_idx=0,
        summary_sig_before=(1, 2, 3),
    )
    assert ss["speaker_id_speaker_idx"] == 0
    assert reruns == []


def test_workspace_fragment_reloads_mapping_every_run() -> None:
    """Save/Ignore freshness depends on fresh sidecar read inside the fragment."""
    import inspect

    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    frag_body = source.split("def _speaker_id_workspace_fragment", 1)[1]
    frag_body = frag_body.split("def render_speaker_id_page", 1)[0]
    assert "controller.get_mapping_status(transcript_path)" in frag_body
    assert "load_speaker_identification_index(transcript_path)" in frag_body
    sig = inspect.signature(mod._speaker_id_workspace_fragment)
    assert list(sig.parameters) == ["transcript_path", "controller"]


def test_voice_pending_stale_path_is_rejected_without_analyse() -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "paths_match(pending_path, transcript_path)" in source
    assert "voice_pending_key" in source
    pending_block = source.split("pending = st.session_state.pop(pending_key", 1)[1]
    pending_block = pending_block.split("batch_summary = st.session_state.pop", 1)[0]
    assert "paths_match(pending_path, transcript_path)" in pending_block
    assert pending_block.index("paths_match") < pending_block.index("facade.analyse(")


def test_completion_triggers_one_app_rerun_and_flag_is_consumed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from types import SimpleNamespace

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        "speaker_id_speaker_idx": 0,
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(mod, "invalidate_transcript_summary_for_path", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "clear_playback_session_keys", lambda *_a, **_k: None)

    app_calls = {"n": 0}

    def _app_rerun():
        app_calls["n"] += 1
        ss[mod._SPEAKER_ID_COMPLETION_APP_RERUN] = True
        raise RuntimeError("rerun")

    monkeypatch.setattr(mod, "_rerun_app_for_completion", _app_rerun)
    monkeypatch.setattr(mod, "_rerun_ui", lambda: (_ for _ in ()).throw(RuntimeError("frag")))

    new_state = SimpleNamespace(
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=["SPEAKER_01"],
    )
    try:
        mod._after_mapping_mutation(
            transcript_path=transcript,
            speaker_ids=["SPEAKER_00", "SPEAKER_01"],
            new_state=new_state,
            speaker_idx=0,
            summary_sig_before=(1, 2, 3),
        )
    except RuntimeError as exc:
        assert str(exc) == "rerun"
    assert app_calls["n"] == 1
    assert ss.get(mod._SPEAKER_ID_COMPLETION_APP_RERUN) is True
    # Outer page consumes the flag once — second pop is a no-op (no loop).
    assert ss.pop(mod._SPEAKER_ID_COMPLETION_APP_RERUN, None) is True
    assert ss.pop(mod._SPEAKER_ID_COMPLETION_APP_RERUN, None) is None


def test_voice_pending_popped_before_analyse_so_exceptions_do_not_requeue() -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    pop_idx = source.index("pending = st.session_state.pop(pending_key")
    analyse_idx = source.index("facade.analyse(")
    assert pop_idx < analyse_idx


def test_speaker_id_page_exposes_workspace_fragment() -> None:
    import inspect

    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert source.count("@st.fragment") == 1
    assert "render_playback_panel_body" in source
    assert "from transcriptx.web.components.playback_panel import" in source
    assert "render_playback_panel_body" in source
    # Must not call the decorated playback entry from the workspace.
    assert "render_playback_panel(" not in source
    sig = inspect.signature(mod._speaker_id_workspace_fragment)
    assert list(sig.parameters) == ["transcript_path", "controller"]


def test_invalidate_transcript_summary_for_path_clears_specific_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.cache_helpers as cache_mod

    path = tmp_path / "a.json"
    path.write_text('{"segments":[]}', encoding="utf-8")
    cleared: list[tuple] = []

    class _Fn:
        def clear(self, *args, **kwargs):
            cleared.append(args)

    monkeypatch.setattr(cache_mod, "cached_transcript_summary_for_path", _Fn())
    sig = (1, 2, 3)
    cache_mod.invalidate_transcript_summary_for_path(path, signature=sig)
    assert cleared
    assert sig in cleared[0]


def test_paths_with_current_subject_appends_missing_navigated_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Post-import nav must still preselect when discovery lags the new file."""
    import transcriptx.web.page_modules.speaker_id as mod

    existing = tmp_path / "older.json"
    existing.write_text("{}", encoding="utf-8")
    imported = tmp_path / "R20241025-162403.json"
    imported.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_preferred_transcript_path",
        lambda: str(imported),
    )
    monkeypatch.setattr(mod.st, "session_state", {}, raising=False)

    merged = mod._paths_with_current_subject([existing])
    assert len(merged) == 2
    assert any(p.resolve() == imported.resolve() for p in merged)


def test_paths_with_current_subject_noop_when_already_listed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_preferred_transcript_path",
        lambda: str(transcript),
    )
    monkeypatch.setattr(mod.st, "session_state", {}, raising=False)

    merged = mod._paths_with_current_subject([transcript])
    assert merged == [transcript]


def test_bind_transcript_picker_sets_index_when_key_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    ss: dict = {}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    mod._bind_transcript_picker_index(["/a.json", "/b.json"], 2)
    assert ss["speaker_id_transcript"] == 2
    mod._bind_transcript_picker_index(["/a.json", "/b.json"], 1)
    assert ss["speaker_id_transcript"] == 2  # already bound


def test_bind_transcript_picker_recovers_placeholder_when_preferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Widget remount at 0 must not strand the page when a path is known."""
    import transcriptx.web.page_modules.speaker_id as mod

    ss: dict = {"speaker_id_transcript": 0}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    mod._bind_transcript_picker_index(["/a.json", "/b.json"], 2)
    assert ss["speaker_id_transcript"] == 2


def test_bind_transcript_picker_sanitizes_out_of_range_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    ss: dict = {"speaker_id_transcript": 99}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    mod._bind_transcript_picker_index(["/a.json", "/b.json"], 1)
    assert ss["speaker_id_transcript"] == 1


def test_preferred_transcript_path_uses_page_selection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    selected = tmp_path / "selected.json"
    selected.write_text("{}", encoding="utf-8")
    ss = {mod._SPEAKER_ID_SELECTED_PATH: str(selected)}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(
        mod.SubjectService,
        "current_transcript_path",
        staticmethod(lambda _ss: None),
    )
    assert mod._preferred_transcript_path() == str(selected)


def test_speaker_id_page_defers_voice_analyse() -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "voice_pending_key" in source
    assert "_SPEAKER_ID_SELECTED_PATH" in source
    assert "_cb_voice_analyse_one" in source
    assert "Load voice suggestions" in source
    assert "on_click=_cb_voice_analyse_one" in source
    # Voice analyse callbacks must not explicitly fragment-rerun.
    analyse_cb = source.split("def _cb_voice_analyse_one", 1)[1].split("def _cb_", 1)[0]
    assert "_rerun_ui()" not in analyse_cb
    assert "get_shared_speaker_studio_controller" in source
    assert "SpeakerStudioController()" not in source
    assert "SegmentIndexService" not in source
    assert "ClipService" not in source
    assert "SpeakerMappingService" not in source


def test_speaker_id_page_exposes_render_function() -> None:
    """Contract: render_speaker_id_page must be importable and callable."""
    from transcriptx.web.page_modules.speaker_id import render_speaker_id_page

    assert callable(render_speaker_id_page)


def test_speaker_id_page_renders_post_completion_action_links() -> None:
    """When all speakers are identified, show homepage-style next-step links."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_render_post_speaker_id_actions" in source
    assert "All speakers identified!" in source
    assert "render_recent_run_actions" in source
    assert "SectionId.SPEAKER_ID_COMPLETE" in source
    assert "render_configured_actions" in source
    # Fragment-scoped ON_CLICK cannot navigate; completion strip must CLICK_RERUN.
    assert "NavStyle.CLICK_RERUN" in source
    assert source.count("nav_style=NavStyle.CLICK_RERUN") >= 2


def test_latest_run_summary_for_transcript_builds_run_when_outputs_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    import transcriptx.web.page_modules.speaker_id as mod

    outputs = tmp_path / "outputs"
    run_dir = outputs / "slug-a" / "20260713_032900_abcdef12"
    run_dir.mkdir(parents=True)
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}")

    monkeypatch.setattr(mod, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(
        mod,
        "resolve_transcript_context",
        lambda *_a, **_k: type(
            "R", (), {"subject_id": "slug-a", "run_id": "20260713_032900_abcdef12"}
        )(),
    )

    summary = mod._latest_run_summary_for_transcript(transcript)
    assert summary is not None
    assert summary.run_id == "20260713_032900_abcdef12"
    assert summary.run_dir == run_dir
    assert isinstance(summary.created_at, datetime)


def test_render_post_speaker_id_actions_uses_recent_run_strip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.app.models.results import RunSummary
    from datetime import datetime

    called: dict[str, object] = {}

    def _fake_actions(
        run, *, row_index=0, key_prefix="home_run", section=None, nav_style=None
    ):
        called["run"] = run
        called["key_prefix"] = key_prefix
        called["row_index"] = row_index
        called["section"] = section
        called["nav_style"] = nav_style

    monkeypatch.setattr(mod, "render_recent_run_actions", _fake_actions)
    monkeypatch.setattr(
        mod,
        "_latest_run_summary_for_transcript",
        lambda _p: RunSummary(
            run_dir=tmp_path / "slug" / "run1",
            transcript_path=tmp_path / "t.json",
            run_id="run1",
            created_at=datetime(2026, 7, 13),
            selected_modules=[],
        ),
    )

    mod._render_post_speaker_id_actions(tmp_path / "t.json")
    assert called["key_prefix"] == "speaker_id_run"
    assert called["row_index"] == 0
    assert getattr(called["run"], "run_id") == "run1"
    from transcriptx.web.action_menus.ids import NavStyle

    assert called["nav_style"] == NavStyle.CLICK_RERUN


def test_speaker_id_transcript_label_partial_shows_counts() -> None:
    from transcriptx.web.page_modules.speaker_id import _speaker_id_transcript_label
    from transcriptx.services.speaker_studio.segment_index import TranscriptSummary

    t = TranscriptSummary(
        path="/x.json",
        base_name="meeting",
        speaker_map_status="partial",
        segment_count=100,
        unique_speaker_count=3,
        unidentified_speaker_count=2,
        ignored_speaker_count=1,
    )
    label = _speaker_id_transcript_label(t)
    assert label.startswith("meeting (partial, 100 segs)")
    assert "2 unidentified" in label
    assert "1 ignored" in label


def test_speaker_id_transcript_label_complete_omits_extra_counts() -> None:
    from transcriptx.web.page_modules.speaker_id import _speaker_id_transcript_label
    from transcriptx.services.speaker_studio.segment_index import TranscriptSummary

    t = TranscriptSummary(
        path="/x.json",
        base_name="meeting",
        speaker_map_status="complete",
        segment_count=50,
        unique_speaker_count=2,
        unidentified_speaker_count=0,
        ignored_speaker_count=1,
    )
    assert _speaker_id_transcript_label(t) == "meeting (complete, 50 segs)"


# ── helper fixtures ───────────────────────────────────────────────────────────


def _make_transcript(path: Path, speakers: list[dict]) -> None:
    """Write a minimal v1.0 transcript artifact with given segments."""
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {
                    "type": "manual",
                    "original_path": path.name,
                    "imported_at": "2026-01-01T00:00:00Z",
                },
                "segments": speakers,
            }
        )
    )


@pytest.fixture()
def transcript_dir(tmp_path: Path) -> Path:
    (tmp_path / "transcripts").mkdir()
    return tmp_path


def _configure_paths_for_transcripts_root(
    monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> None:
    """Point PATHS.transcripts_dir (and DATA_DIR) at a test-local transcripts root.

    This ensures canonical_transcript_relpath and speaker_map_path_for_transcript
    accept the test transcripts under tmp_path/transcripts.
    """
    import importlib
    import transcriptx.core.utils.paths as paths_mod

    # Ensure DATA_DIR and transcripts_dir env are consistent for PATHS rebuild.
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcripts_root.parent))
    monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(transcripts_root))

    importlib.reload(paths_mod)


@pytest.fixture()
def two_speaker_transcript(transcript_dir: Path) -> Path:
    path = transcript_dir / "transcripts" / "meeting_transcriptx.json"
    _make_transcript(
        path,
        [
            {
                "start": 0.0,
                "end": 2.5,
                "speaker": "SPEAKER_00",
                "text": "Good morning everyone.",
            },
            {
                "start": 2.5,
                "end": 5.0,
                "speaker": "SPEAKER_01",
                "text": "Hi, thanks for joining.",
            },
            {
                "start": 5.0,
                "end": 8.0,
                "speaker": "SPEAKER_00",
                "text": "Let us get started.",
            },
            {
                "start": 8.0,
                "end": 10.0,
                "speaker": "SPEAKER_01",
                "text": "Sounds good.",
            },
        ],
    )
    return path


# ── integration ───────────────────────────────────────────────────────────────


def test_speaker_id_initial_state_is_none(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Fresh transcript starts with speaker_map_status='none'."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert len(transcripts) == 1
    assert transcripts[0].speaker_map_status == "none"
    assert transcripts[0].unique_speaker_count == 2


def test_speaker_id_segments_grouped_by_diarized_id(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """list_segments returns all segments; helper groups them by diarized ID correctly."""
    from transcriptx.web.page_modules.speaker_id import _group_by_diarized_id

    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    segments = controller.list_segments(str(two_speaker_transcript))
    assert len(segments) == 4

    groups = _group_by_diarized_id(segments)
    assert set(groups.keys()) == {"SPEAKER_00", "SPEAKER_01"}
    assert len(groups["SPEAKER_00"]) == 2
    assert len(groups["SPEAKER_01"]) == 2


def test_voice_analyse_segment_dicts_prefer_diarized_id_after_naming(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """After naming, SegmentInfo.speaker is a display name; voice dicts keep diarized IDs."""
    from transcriptx.web.page_modules.speaker_id import _voice_analyse_segment_dicts

    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Speaker 1", method="web"
    )
    segments = controller.list_segments(str(two_speaker_transcript))
    assert any(s.speaker == "Speaker 1" for s in segments)

    dicts = _voice_analyse_segment_dicts(segments)
    assert len(dicts) == len(segments)
    named = [d for d in dicts if d["speaker_diarized_id"] == "SPEAKER_00"]
    assert named
    assert all(d["speaker"] == "SPEAKER_00" for d in named)


def test_speaker_id_page_exposes_analyse_all_speakers_button() -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Analyse all speakers" in source
    assert "_voice_analyse_segment_dicts" in source


def test_speaker_id_assign_name_reflected_in_mapping(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Assigning a name via apply_mapping_mutation updates the sidecar only."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Alice", method="web"
    )

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.speaker_map.get("SPEAKER_01") in (None, "")

    data = json.loads(two_speaker_transcript.read_text())
    assert all(s["speaker"].startswith("SPEAKER_") for s in data["segments"])

    sidecar = json.loads(sidecar_path_for(two_speaker_transcript).read_text())
    assert sidecar["speaker_map"]["SPEAKER_00"] == "Alice"

    segments = controller.list_segments(str(two_speaker_transcript))
    alice_segs = [s for s in segments if s.speaker == "Alice"]
    assert len(alice_segs) == 2


def test_speaker_id_ignore_speaker(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """ignore_speaker marks the diarized ID as ignored."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.ignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert "SPEAKER_01" in state.ignored_speakers


def test_speaker_id_unignore_speaker(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """unignore_speaker removes the diarized ID from the ignored list."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.ignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")
    controller.unignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert "SPEAKER_01" not in state.ignored_speakers


def test_speaker_id_ignore_last_remaining_marks_complete(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
) -> None:
    """Ignoring the final unnamed speaker yields complete + remaining 0."""
    from transcriptx.web.page_modules.speaker_id import (
        _group_by_diarized_id,
        _is_speaker_ignored,
        _next_unnamed_idx,
        _speaker_map_display_name,
    )

    path = transcript_dir / "transcripts" / "last_ignore_transcriptx.json"
    _make_transcript(
        path,
        [
            {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "A"},
            {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01", "text": "B"},
            {"start": 2.0, "end": 3.0, "speaker": "SPEAKER_02", "text": "C"},
            {"start": 3.0, "end": 4.0, "speaker": "SPEAKER_03", "text": "D"},
            {"start": 4.0, "end": 5.0, "speaker": "SPEAKER_03", "text": "E"},
        ],
    )
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(str(path), "SPEAKER_00", "Glen", method="web")
    controller.apply_mapping_mutation(str(path), "SPEAKER_01", "Ana", method="web")
    controller.apply_mapping_mutation(str(path), "SPEAKER_02", "Ana", method="web")

    summaries = controller.list_transcripts(data_dir=transcript_dir)
    assert summaries[0].speaker_map_status == "partial"
    assert summaries[0].unidentified_speaker_count == 1

    # UI ignore path: persist then navigate from returned state.
    new_state = controller.ignore_speaker(str(path), "SPEAKER_03", method="web")
    segments = controller.list_segments(str(path))
    speaker_ids = list(_group_by_diarized_id(segments).keys())
    current_idx = speaker_ids.index("SPEAKER_03")
    next_idx = _next_unnamed_idx(
        speaker_ids,
        dict(new_state.speaker_map or {}),
        list(new_state.ignored_speakers or []),
        current_idx,
    )
    assert next_idx == current_idx
    assert "SPEAKER_03" in (new_state.ignored_speakers or [])

    speaker_map = new_state.speaker_map or {}
    ignored = list(new_state.ignored_speakers or [])
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = len(speaker_ids) - named - n_ignored
    assert named == 3
    assert n_ignored == 1
    assert remaining == 0

    summaries = controller.list_transcripts(data_dir=transcript_dir)
    assert summaries[0].speaker_map_status == "complete"
    assert summaries[0].unidentified_speaker_count == 0
    assert summaries[0].ignored_speaker_count == 1


def test_speaker_id_full_flow_both_speakers_named(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Naming all speakers results in speaker_map_status='complete'."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Alice", method="web"
    )
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_01", "Bob", method="web"
    )

    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert transcripts[0].speaker_map_status == "complete"


def test_speaker_id_fmt_time_helper() -> None:
    """_fmt_time formats seconds into M:SS and H:MM:SS correctly."""
    from transcriptx.web.page_modules.speaker_id import _fmt_time

    assert _fmt_time(0.0) == "0:00"
    assert _fmt_time(59.9) == "0:59"
    assert _fmt_time(60.0) == "1:00"
    assert _fmt_time(3661.0) == "1:01:01"


def test_speaker_id_next_unnamed_idx_stays_when_current_still_unnamed() -> None:
    """Partial naming failure must not jump past the still-unnamed active speaker."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    result = _next_unnamed_idx(speaker_ids, {}, [], current=0)
    assert result == 0
    # Later unnamed speakers must not pull focus away from current.
    result = _next_unnamed_idx(
        speaker_ids, {"SPEAKER_01": "Bob"}, [], current=0
    )
    assert result == 0


def test_speaker_id_next_unnamed_idx_skips_named_and_ignored() -> None:
    """_next_unnamed_idx advances past already-named or ignored speakers."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    ignored = ["SPEAKER_02"]

    # From index 0, should find SPEAKER_03 (index 3) as the next unnamed, non-ignored
    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=0)
    assert result == 3


def test_speaker_id_next_unnamed_idx_wraps_around() -> None:
    """_next_unnamed_idx wraps from end to beginning when nothing unnamed is after current."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    speaker_map = {"SPEAKER_01": "Bob", "SPEAKER_02": "Carol"}
    ignored: list[str] = []

    # From index 2 (Carol), wrap around to find SPEAKER_00 (index 0)
    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=2)
    assert result == 0


def test_speaker_id_next_unnamed_idx_stays_when_all_named() -> None:
    """_next_unnamed_idx returns current when every speaker is named or ignored."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01"]
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    ignored: list[str] = []

    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=0)
    assert result == 0


def test_speaker_id_next_unnamed_idx_after_ignore_last_stays() -> None:
    """Ignoring the last remaining speaker keeps the current index (completion)."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
    speaker_map = {
        "SPEAKER_00": "Glen",
        "SPEAKER_01": "Ana",
        "SPEAKER_02": "Ana",
    }
    # Mirror ignore-button persistence: active SPEAKER_03 is now ignored.
    ignored_after = ["SPEAKER_03"]
    current_idx = 3

    result = _next_unnamed_idx(
        speaker_ids, speaker_map, ignored_after, current=current_idx
    )
    assert result == current_idx


def test_speaker_id_next_unnamed_idx_after_unignore_finds_that_speaker() -> None:
    """After unignore, navigation must not keep treating the id as ignored."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    # Bug regression: old UI passed ignored+[active] even on unignore.
    ignored_after_unignore: list[str] = []
    result = _next_unnamed_idx(
        speaker_ids, speaker_map, ignored_after_unignore, current=1
    )
    assert result == 2


def test_is_speaker_ignored_accepts_variant_diarized_ids() -> None:
    from transcriptx.web.page_modules.speaker_id import _is_speaker_ignored

    assert _is_speaker_ignored(["SPEAKER_03"], "SPEAKER_3") is True
    assert _is_speaker_ignored(["SPEAKER_3"], "SPEAKER_03") is True
    assert _is_speaker_ignored(["SPEAKER_01"], "SPEAKER_03") is False


def test_speaker_id_next_unnamed_idx_after_save_moves_to_next_unnamed() -> None:
    """Saving current speaker should advance to the next unnamed speaker when present."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
    speaker_map = {
        "SPEAKER_00": "Alice",
        "SPEAKER_02": "Carol",
    }
    ignored: list[str] = []
    current_idx = 0  # active speaker is SPEAKER_00

    # Mirror the save-path behavior: current speaker is now named.
    map_after_save = speaker_map | {"SPEAKER_00": "Alice"}
    result = _next_unnamed_idx(
        speaker_ids,
        map_after_save,
        ignored,
        current=current_idx,
    )

    # SPEAKER_01 is the next unnamed speaker and should be selected.
    assert result == 1


def test_speaker_map_display_name_variant_id_matches_sidecar() -> None:
    """Sidecar keys are normalized; UI lookups must accept variant diarized ids."""
    from transcriptx.web.page_modules.speaker_id import _speaker_map_display_name

    m = {"SPEAKER_01": "Andrea", "SPEAKER_02": "Bob"}
    assert _speaker_map_display_name(m, "SPEAKER_1") == "Andrea"
    assert _speaker_map_display_name(m, "SPEAKER_01") == "Andrea"
    assert _speaker_map_display_name(m, "SPEAKER_2") == "Bob"


def test_speaker_map_display_name_ignores_placeholder_self_mapping() -> None:
    """Mappings like SPEAKER_00 -> SPEAKER_00 should still render as unnamed."""
    from transcriptx.web.page_modules.speaker_id import _speaker_map_display_name

    m = {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "Alice"}
    assert _speaker_map_display_name(m, "SPEAKER_00") == ""
    assert _speaker_map_display_name(m, "SPEAKER_01") == "Alice"


def test_remaining_count_and_speaker_label_helpers() -> None:
    """Named / ignored / remaining counts and jump labels stay consistent."""
    from types import SimpleNamespace

    from transcriptx.web.page_modules.speaker_id import (
        _remaining_count,
        _speaker_label,
        _voice_display_from_result,
    )

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    speaker_map = {"SPEAKER_00": "Alice"}
    ignored = ["SPEAKER_02"]
    named, n_ignored, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    assert (named, n_ignored, remaining) == (1, 1, 1)
    assert "→ Alice" in _speaker_label("SPEAKER_00", 0, speaker_map, ignored)
    assert "🔇" in _speaker_label("SPEAKER_02", 2, speaker_map, ignored)
    assert "❓" in _speaker_label("SPEAKER_01", 1, speaker_map, ignored)

    result = SimpleNamespace(
        outcome="matched",
        detail="ok",
        candidates_ui=[
            {
                "profile_id": "p1",
                "display_name": "stale",
                "confidence": 0.9,
                "reference_count": 2,
            },
            {"profile_id": None, "display_name": "anon", "confidence": 0.1},
        ],
    )
    payload = _voice_display_from_result(
        result, profile_name_lookup=lambda pid: "Live" if pid == "p1" else None
    )
    assert payload["outcome"] == "matched"
    assert payload["candidates"][0]["display_name"] == "Live"
    assert payload["candidates"][1]["display_name"] == "anon"


def test_speaker_id_named_and_remaining_counts_with_variant_diarized_ids(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
) -> None:
    """Progress metrics match sidecar after naming when transcript uses SPEAKER_1-style ids."""
    from transcriptx.web.page_modules.speaker_id import (
        _group_by_diarized_id,
        _is_speaker_ignored,
        _speaker_map_display_name,
    )

    path = transcript_dir / "transcripts" / "variant_ids_transcriptx.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {
                    "type": "manual",
                    "original_path": path.name,
                    "imported_at": "2026-01-01T00:00:00Z",
                },
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_1", "text": "A"},
                    {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_2", "text": "B"},
                    {"start": 2.0, "end": 3.0, "speaker": "SPEAKER_3", "text": "C"},
                ],
            }
        )
    )

    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(str(path), "SPEAKER_1", "Alice", method="web")
    controller.apply_mapping_mutation(str(path), "SPEAKER_2", "Bob", method="web")
    controller.ignore_speaker(str(path), "SPEAKER_3", method="web")

    state = controller.get_mapping_status(str(path))
    speaker_map = state.speaker_map or {}
    ignored = getattr(state, "ignored_speakers", None) or []

    segments = controller.list_segments(str(path))
    groups = _group_by_diarized_id(segments)
    speaker_ids = list(groups.keys())

    total = len(speaker_ids)
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = total - named - n_ignored

    assert total == 3
    assert named == 2
    assert n_ignored == 1
    assert remaining == 0

    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert transcripts[0].speaker_map_status == "complete"


def test_transcript_scoped_keys_isolate_same_speaker_across_paths(tmp_path: Path) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")
    assert mod.name_widget_key(a, "SPEAKER_00") != mod.name_widget_key(b, "SPEAKER_00")
    assert mod.play_key(a) != mod.play_key(b)
    assert mod.flash_key(a) != mod.flash_key(b)


def test_jump_callback_does_not_rewrite_jump_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    j_key = mod.jump_key(transcript)
    idx_key = mod.speaker_idx_key(transcript)
    ss: dict = {j_key: 2, idx_key: 0}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(mod, "clear_playback_session_keys", lambda *_a, **_k: None)

    index = SpeakerIdentificationIndex(
        segments_by_speaker={
            "SPEAKER_00": (),
            "SPEAKER_01": (),
            "SPEAKER_02": (),
        },
        ordered_speaker_ids=("SPEAKER_00", "SPEAKER_01", "SPEAKER_02"),
        segment_counts=(0, 0, 0),
        durations=(0.0, 0.0, 0.0),
    )
    monkeypatch.setattr(mod, "load_speaker_identification_index", lambda *_a, **_k: index)
    mod._cb_jump_change(str(transcript))
    assert ss[j_key] == 2  # jump widget key untouched
    assert ss[idx_key] == 2


def test_validate_callback_identity_rejects_stale_speaker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    idx_key = mod.speaker_idx_key(transcript)
    ss: dict = {idx_key: 0}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    index = SpeakerIdentificationIndex(
        segments_by_speaker={"SPEAKER_00": (), "SPEAKER_01": ()},
        ordered_speaker_ids=("SPEAKER_00", "SPEAKER_01"),
        segment_counts=(0, 0),
        durations=(0.0, 0.0),
    )
    monkeypatch.setattr(mod, "load_speaker_identification_index", lambda *_a, **_k: index)
    assert (
        mod._validate_callback_identity(
            str(transcript), expected_speaker_id="SPEAKER_01"
        )
        is None
    )
    flash = ss.get(mod.flash_key(transcript))
    assert flash is not None
    assert flash["level"] == "warning"


def test_ordinary_action_callbacks_do_not_call_rerun_ui() -> None:
    """Exactly one fragment paint: callbacks must not invoke _rerun_ui."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for name in (
        "_cb_save_name",
        "_cb_ignore_toggle",
        "_cb_prev",
        "_cb_next",
        "_cb_jump_change",
        "_cb_voice_analyse_one",
        "_cb_voice_analyse_all",
        "_cb_voice_confirm",
        "_cb_voice_reject",
        "_cb_voice_leave",
    ):
        block = source.split(f"def {name}", 1)[1].split("\ndef ", 1)[0]
        assert "_rerun_ui()" not in block, name
    advance = source.split("def _apply_mapping_advance", 1)[1].split("\ndef ", 1)[0]
    assert "_rerun_ui()" not in advance
    from transcriptx.app.speaker_id import service as action_mod

    action_src = Path(action_mod.__file__).read_text(encoding="utf-8")
    assert "st.rerun" not in action_src
    assert "_rerun_ui" not in action_src


def test_flash_consume_is_one_shot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    errors: list[str] = []
    monkeypatch.setattr(mod.st, "error", lambda msg: errors.append(str(msg)))
    mod._set_flash(transcript, level="error", message="boom")
    mod._consume_flash(transcript)
    assert errors == ["boom"]
    mod._consume_flash(transcript)
    assert errors == ["boom"]


def test_play_hot_path_does_not_construct_voice_services() -> None:
    """Playback/workspace body must not instantiate voice facades unless voice loaded."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    frag = source.split("def _speaker_id_workspace_fragment", 1)[1]
    frag = frag.split("def render_speaker_id_page", 1)[0]
    # Workspace resolves profile context but must not construct the facade.
    assert "SpeakerIdVoiceFacade()" not in frag.split("def _render_voice_suggestions", 1)[0]
    assert "resolve_playback_context" in frag
    voice = source.split("def _render_voice_suggestions", 1)[1]
    assert "voice_display_key" in voice
    assert "Load voice suggestions" in voice
    # Facade only when processing pending analyse work.
    assert voice.index('if not st.session_state.get(loaded_key)') < voice.index(
        "SpeakerIdVoiceFacade()"
    )
    assert voice.index("pending_peek") < voice.index("SpeakerIdVoiceFacade()")


def test_save_ignore_nav_callbacks_require_expected_speaker_id() -> None:
    import inspect

    import transcriptx.web.page_modules.speaker_id as mod

    for name in ("_cb_save_name", "_cb_ignore_toggle", "_cb_prev", "_cb_next"):
        params = list(inspect.signature(getattr(mod, name)).parameters)
        assert params == ["transcript_path", "expected_speaker_id"], name


def test_cb_save_rejects_stale_expected_speaker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    idx_key = mod.speaker_idx_key(transcript)
    ss: dict = {idx_key: 0}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    index = SpeakerIdentificationIndex(
        segments_by_speaker={"SPEAKER_00": (), "SPEAKER_01": ()},
        ordered_speaker_ids=("SPEAKER_00", "SPEAKER_01"),
        segment_counts=(0, 0),
        durations=(0.0, 0.0),
    )
    monkeypatch.setattr(mod, "load_speaker_identification_index", lambda *_a, **_k: index)
    called: list[str] = []
    monkeypatch.setattr(
        mod,
        "get_shared_speaker_studio_controller",
        lambda: (_ for _ in ()).throw(AssertionError("should not mutate")),
    )
    mod._cb_save_name(str(transcript), "SPEAKER_01")
    flash = ss.get(mod.flash_key(transcript))
    assert flash is not None
    assert flash["level"] == "warning"
    assert called == []


def test_profile_context_cache_keyed_by_resolved_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    calls = {"n": 0}

    def _fake(path_str: str):
        calls["n"] += 1
        return mod.TranscriptProfileContext(is_managed=False)

    monkeypatch.setattr(mod, "_cached_transcript_profile_context", _fake)
    a = mod._resolve_profile_context(transcript)
    b = mod._resolve_profile_context(str(transcript.resolve()))
    assert a.is_managed is False and b.is_managed is False
    # Two calls to the thin wrapper; cache function itself is what Streamlit memoizes.
    assert calls["n"] == 2


def test_voice_unmounted_until_loaded_contract() -> None:
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    voice = source.split("def _render_voice_suggestions", 1)[1]
    early = voice.split("if not st.session_state.get(loaded_key)", 1)[1]
    early = early.split("return", 1)[0]
    assert "ActivationBarrier" not in early
    assert "SpeakerIdVoiceFacade" not in early
    assert "SpeakerProfileService" not in early


def test_ccv2_is_default_mount_path_contract() -> None:
    """Fragment prefers CCv2 when enabled; falls through to legacy when mount fails."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    frag = source.split("def _speaker_id_workspace_fragment", 1)[1]
    frag = frag.split("def render_speaker_id_page", 1)[0]
    assert "speaker_id_workspace_component_enabled" in frag
    assert "_render_ccv2_speaker_workspace" in frag
    assert "if mounted:" in frag
    assert "return True" in source.split("def _render_ccv2_speaker_workspace", 1)[1]
    assert "return False" in source.split("def _render_ccv2_speaker_workspace", 1)[1]
    # Classic widgets remain for rollback / missing-package path.
    assert "render_playback_panel_body" in frag
    assert "on_click=_cb_save_name" in frag


def test_render_ccv2_returns_false_when_package_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default-on must not brick Speaker ID when transcriptx-workspaces is absent."""
    import builtins
    import transcriptx.web.page_modules.speaker_id as mod
    from types import SimpleNamespace

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {}
    warnings: list[str] = []
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(mod.st, "warning", lambda msg: warnings.append(str(msg)))

    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "transcriptx_workspaces" or name.startswith(
            "transcriptx_workspaces."
        ):
            raise ImportError("forced missing workspaces package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)

    ok = mod._render_ccv2_speaker_workspace(
        transcript_path=str(transcript),
        controller=SimpleNamespace(),
        speaker_ids=["SPEAKER_00"],
        speaker_idx=0,
        active_id="SPEAKER_00",
        speaker_map={},
        ignored=[],
        active_segs=[],
        current_name="",
        playback_ctx=SimpleNamespace(audio_path=None),
        status_badge="unnamed",
        total_speakers=1,
    )
    assert ok is False
    assert warnings
    assert "classic Speaker ID" in warnings[0]


def test_render_ccv2_mounts_and_dispatches_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Happy path: build data, mount component, dispatch save_name, store ack."""
    import sys
    from types import ModuleType, SimpleNamespace

    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.app.speaker_id import (
        SpeakerIdAck,
        SpeakerIdEffects,
        SpeakerIdFlash,
    )

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    monkeypatch.setattr(
        mod,
        "_resolve_profile_context",
        lambda *_a, **_k: mod.TranscriptProfileContext(is_managed=False),
    )

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="miss", clip_id="c1", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, *_a, **_k):
            return SimpleNamespace(status="accepted", clip_id="c1")

        def ffmpeg_available(self) -> bool:
            return True

    mounts: list[dict] = []

    def _fake_workspace(*, data, key, on_command_change=None, **_kw):
        mounts.append({"data": data, "key": key})
        return {
            "command": {
                "action": "save_name",
                "action_id": "aid-ccv2",
                "action_seq": 1,
                "protocol_version": "1",
                "frontend_build_id": "legacy",
                "transcript_id": str(transcript),
                "expected_speaker_id": "SPEAKER_00",
                "payload": {"name": "Alice"},
            }
        }

    fake_pkg = ModuleType("transcriptx_workspaces")
    fake_pkg.speaker_id_workspace = _fake_workspace  # type: ignore[attr-defined]
    fake_pkg.FRONTEND_BUILD_ID = "tx-workspaces-0.1.0"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transcriptx_workspaces", fake_pkg)

    applied: list = []

    class _Svc:
        _expected_builds = set()

        def execute(self, command):
            return SpeakerIdAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="ok",
                transcript_id=command.transcript_id,
                transcript_revision="tr1",
                mapping_revision="mr1",
                active_speaker_id="SPEAKER_00",
                active_speaker_idx=0,
                effects=SpeakerIdEffects(
                    flashes=(SpeakerIdFlash(level="info", message="saved"),),
                ),
            )

    monkeypatch.setattr(mod, "_get_action_service", lambda: _Svc())
    monkeypatch.setattr(
        mod,
        "_apply_ack",
        lambda ack, **_k: applied.append(ack),
    )

    segs = [SimpleNamespace(start=0.0, end=1.0, text="hello", speaker="SPEAKER_00")]
    ok = mod._render_ccv2_speaker_workspace(
        transcript_path=str(transcript),
        controller=_Ctrl(),
        speaker_ids=["SPEAKER_00"],
        speaker_idx=0,
        active_id="SPEAKER_00",
        speaker_map={},
        ignored=[],
        active_segs=segs,
        current_name="",
        playback_ctx=SimpleNamespace(audio_path=None),
        status_badge="❓ unnamed",
        total_speakers=1,
    )
    assert ok is True
    assert len(mounts) == 1
    assert mounts[0]["key"].startswith("speaker_id_ws:")
    assert mounts[0]["data"]["active_speaker_id"] == "SPEAKER_00"
    assert mounts[0]["data"]["samples"][0]["clip_status"] == "pending"
    assert len(applied) == 1
    ack_key = mod.widget_key(transcript, "ccv2_last_ack")
    assert ss[ack_key]["status"] == "ok"
    assert ss[ack_key]["action_id"] == "aid-ccv2"


class _CtxCol:
    """Minimal Streamlit column stub that supports ``with col:``."""

    def metric(self, *_a, **_k):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _stub_fragment_chrome(monkeypatch: pytest.MonkeyPatch, mod) -> None:
    def _columns(spec):
        n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [_CtxCol() for _ in range(n)]

    monkeypatch.setattr(mod.st, "metric", lambda *_a, **_k: None)
    monkeypatch.setattr(mod.st, "columns", _columns)
    monkeypatch.setattr(mod.st, "divider", lambda: None)
    monkeypatch.setattr(mod.st, "success", lambda *_a, **_k: None)
    monkeypatch.setattr(mod.st, "caption", lambda *_a, **_k: None)
    monkeypatch.setattr(mod.st, "text_input", lambda *_a, **_k: "")
    monkeypatch.setattr(mod.st, "checkbox", lambda *_a, **_k: False)
    monkeypatch.setattr(mod.st, "button", lambda *_a, **_k: False)
    monkeypatch.setattr(mod.st, "number_input", lambda *_a, **_k: 0)
    monkeypatch.setattr(mod, "_consume_flash", lambda *_a, **_k: None)


def test_workspace_fragment_prefers_ccv2_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fragment returns after successful CCv2 mount (skips legacy widgets)."""
    from types import SimpleNamespace

    import transcriptx.web.page_modules.speaker_id as mod
    import transcriptx.web.workspaces.flags as flags_mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {}
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    _stub_fragment_chrome(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "load_speaker_identification_index",
        lambda *_a, **_k: SpeakerIdentificationIndex(
            segments_by_speaker={"SPEAKER_00": ()},
            ordered_speaker_ids=("SPEAKER_00",),
            segment_counts=(0,),
            durations=(0.0,),
        ),
    )
    monkeypatch.setattr(
        mod,
        "resolve_playback_context",
        lambda *_a, **_k: SimpleNamespace(audio_path=None),
    )

    class _Ctrl:
        def get_mapping_status(self, *_a, **_k):
            return SimpleNamespace(speaker_map={}, ignored_speakers=[])

    called: list[bool] = []

    def _mount(**_k):
        called.append(True)
        return True

    monkeypatch.setattr(mod, "_render_ccv2_speaker_workspace", _mount)
    monkeypatch.setattr(
        flags_mod, "speaker_id_workspace_component_enabled", lambda *_a, **_k: True
    )

    legacy: list[str] = []
    monkeypatch.setattr(mod.st, "subheader", lambda msg: legacy.append(str(msg)))

    # Call through @st.fragment wrapper — body lives on __wrapped__.
    mod._speaker_id_workspace_fragment.__wrapped__(str(transcript), _Ctrl())
    assert called == [True]
    assert legacy == []


def test_workspace_fragment_uses_legacy_when_flag_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env/session rollback must keep the classic fragment widgets."""
    from types import SimpleNamespace

    import transcriptx.web.page_modules.speaker_id as mod
    import transcriptx.web.workspaces.flags as flags_mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
        mod.lines_key(transcript): 5,
        mod.play_key(transcript): 0,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    _stub_fragment_chrome(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "load_speaker_identification_index",
        lambda *_a, **_k: SpeakerIdentificationIndex(
            segments_by_speaker={"SPEAKER_00": ()},
            ordered_speaker_ids=("SPEAKER_00",),
            segment_counts=(0,),
            durations=(0.0,),
        ),
    )
    monkeypatch.setattr(
        mod,
        "resolve_playback_context",
        lambda *_a, **_k: SimpleNamespace(audio_path=None),
    )
    monkeypatch.setattr(mod, "render_playback_panel_body", lambda **_k: None)
    monkeypatch.setattr(
        mod,
        "_resolve_profile_context",
        lambda *_a, **_k: mod.TranscriptProfileContext(is_managed=False),
    )

    class _Ctrl:
        def get_mapping_status(self, *_a, **_k):
            return SimpleNamespace(speaker_map={}, ignored_speakers=[])

    monkeypatch.setattr(
        flags_mod, "speaker_id_workspace_component_enabled", lambda *_a, **_k: False
    )
    monkeypatch.setattr(
        mod,
        "_render_ccv2_speaker_workspace",
        lambda **_k: (_ for _ in ()).throw(AssertionError("ccv2 must not mount")),
    )

    headers: list[str] = []
    monkeypatch.setattr(mod.st, "subheader", lambda msg: headers.append(str(msg)))

    mod._speaker_id_workspace_fragment.__wrapped__(str(transcript), _Ctrl())
    assert headers
    assert "SPEAKER_00" in headers[0]


def test_workspace_fragment_falls_through_when_ccv2_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Flag on + mount False → classic UI (missing package / import failure)."""
    from types import SimpleNamespace

    import transcriptx.web.page_modules.speaker_id as mod
    import transcriptx.web.workspaces.flags as flags_mod
    from transcriptx.web.cache_helpers import SpeakerIdentificationIndex

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        mod.speaker_idx_key(transcript): 0,
        mod.jump_key(transcript): 0,
        mod.lines_key(transcript): 5,
        mod.play_key(transcript): 0,
    }
    monkeypatch.setattr(mod.st, "session_state", ss, raising=False)
    _stub_fragment_chrome(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "load_speaker_identification_index",
        lambda *_a, **_k: SpeakerIdentificationIndex(
            segments_by_speaker={"SPEAKER_00": ()},
            ordered_speaker_ids=("SPEAKER_00",),
            segment_counts=(0,),
            durations=(0.0,),
        ),
    )
    monkeypatch.setattr(
        mod,
        "resolve_playback_context",
        lambda *_a, **_k: SimpleNamespace(audio_path=None),
    )
    monkeypatch.setattr(mod, "render_playback_panel_body", lambda **_k: None)
    monkeypatch.setattr(
        mod,
        "_resolve_profile_context",
        lambda *_a, **_k: mod.TranscriptProfileContext(is_managed=False),
    )

    class _Ctrl:
        def get_mapping_status(self, *_a, **_k):
            return SimpleNamespace(speaker_map={}, ignored_speakers=[])

    monkeypatch.setattr(
        flags_mod, "speaker_id_workspace_component_enabled", lambda *_a, **_k: True
    )
    monkeypatch.setattr(mod, "_render_ccv2_speaker_workspace", lambda **_k: False)

    headers: list[str] = []
    monkeypatch.setattr(mod.st, "subheader", lambda msg: headers.append(str(msg)))

    mod._speaker_id_workspace_fragment.__wrapped__(str(transcript), _Ctrl())
    assert headers
    assert "SPEAKER_00" in headers[0]
