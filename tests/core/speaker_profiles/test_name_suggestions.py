"""Assistive speaker name suggestions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from transcriptx.core.speaker_profiles.identify.fusion import fuse_speaker_candidates
from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate
from transcriptx.core.speaker_profiles.identify.suggestions.deterministic import (
    build_deterministic_options,
)
from transcriptx.core.speaker_profiles.identify.suggestions.llm_assign import (
    merge_llm_options,
    parse_llm_response,
)
from transcriptx.core.speaker_profiles.identify.suggestions.cache import (
    load_cached_suggestions,
    write_cached_suggestions,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameOption,
    NameSuggestionsResult,
    RosterPerson,
)
from transcriptx.core.speaker_profiles.identify.suggestions.roster import build_roster
from transcriptx.web.workspaces.speaker_id_bridge import build_workspace_data


@pytest.mark.unit
def test_roster_filters_stop_words(monkeypatch) -> None:
    def fake_entities(text: str):
        if "Thanks" in text:
            return [("Thanks", "PERSON")]
        return [("Maya Chen", "PERSON")]

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.suggestions.roster.extract_named_entities",
        fake_entities,
    )
    segments = [
        {"speaker": "SPEAKER_00", "text": "Thanks everyone."},
        {"speaker": "SPEAKER_01", "text": "Maya Chen joined us today."},
    ]
    roster = build_roster(segments)
    names = {p.display_name for p in roster}
    assert "Thanks" not in names
    assert "Maya Chen" in names


@pytest.mark.unit
def test_self_intro_option_for_speaker() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "Hi, I'm Maya."},
        {"speaker": "SPEAKER_01", "text": "Thanks Sam."},
    ]
    roster = (
        RosterPerson("Maya", "maya", 1, ("SPEAKER_00",), "Hi, I'm Maya."),
        RosterPerson("Sam", "sam", 1, ("SPEAKER_01",), "Thanks Sam."),
    )
    opts = build_deterministic_options(segments, roster)
    assert any(o.basis == "self_intro" and o.display_name == "Maya" for o in opts["SPEAKER_00"])


@pytest.mark.unit
def test_vocative_is_a_pickable_option() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "Thanks Alex, that helps."},
        {"speaker": "SPEAKER_01", "text": "No problem."},
    ]
    roster = (RosterPerson("Alex", "alex", 1, ("SPEAKER_00",), "Thanks Alex."),)
    opts = build_deterministic_options(segments, roster)
    assert any(
        o.basis == "vocative" and o.display_name == "Alex"
        for o in opts.get("SPEAKER_01", ())
    )


@pytest.mark.unit
def test_vocative_option_does_not_fuse_apply() -> None:
    mention = ChannelCandidate(
        channel="mention",
        display_name="Sam",
        confidence="possible",
        score=1.0,
        evidence={"primary_kind": "vocative"},
    )
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_01"],
        voice={},
        mentions={"SPEAKER_01": mention},
        style={},
    )
    assert decisions[0].action == "skip"
    assert decisions[0].skip_reason == "abstain"


@pytest.mark.unit
def test_strong_self_intro_still_fuses() -> None:
    mention = ChannelCandidate(
        channel="mention",
        display_name="Maya",
        confidence="strong",
        score=2.0,
        evidence={"primary_kind": "self_intro"},
    )
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={},
        mentions={"SPEAKER_00": mention},
        style={},
    )
    assert decisions[0].action == "apply"
    assert decisions[0].display_name == "Maya"


@pytest.mark.unit
def test_moderator_list_maps_speakers_in_order() -> None:
    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "Welcome. First we have Ana Lee, then Ben Smith, then Cara Wu.",
        },
        {"speaker": "SPEAKER_01", "text": "Happy to be here."},
        {"speaker": "SPEAKER_02", "text": "Thanks for having me."},
        {"speaker": "SPEAKER_03", "text": "Good morning."},
    ]
    roster = tuple(
        RosterPerson(n, n.lower().replace(" ", ""), 1, (), "")
        for n in ("Ana Lee", "Ben Smith", "Cara Wu")
    )
    opts = build_deterministic_options(segments, roster)
    assert any(o.display_name == "Ana Lee" for o in opts.get("SPEAKER_01", ()))
    assert any(o.display_name == "Ben Smith" for o in opts.get("SPEAKER_02", ()))
    assert any(o.display_name == "Cara Wu" for o in opts.get("SPEAKER_03", ()))


@pytest.mark.unit
def test_llm_parser_bad_json_returns_empty() -> None:
    parsed = parse_llm_response(
        "not json {",
        allowed_keys={"maya"},
        speaker_ids={"SPEAKER_00"},
    )
    assert parsed == {}


@pytest.mark.unit
def test_llm_parser_rejects_hallucinated_names() -> None:
    raw = json.dumps(
        {
            "assignments": [
                {
                    "speaker_id": "SPEAKER_00",
                    "display_name": "Zaphod Beeblebrox",
                    "basis": "self_intro",
                    "quote": "hi",
                }
            ]
        }
    )
    parsed = parse_llm_response(
        raw,
        allowed_keys={"maya"},
        speaker_ids={"SPEAKER_00"},
    )
    assert parsed == {}


@pytest.mark.unit
def test_llm_parser_accepts_roster_name() -> None:
    raw = json.dumps(
        {
            "assignments": [
                {
                    "speaker_id": "SPEAKER_00",
                    "display_name": "Maya",
                    "basis": "self_intro",
                    "quote": "I'm Maya",
                }
            ]
        }
    )
    parsed = parse_llm_response(
        raw,
        allowed_keys={"maya"},
        speaker_ids={"SPEAKER_00"},
    )
    assert parsed["SPEAKER_00"].display_name == "Maya"
    assert parsed["SPEAKER_00"].source == "llm"


@pytest.mark.unit
def test_merge_llm_inserts_ahead_of_roster() -> None:
    det = {
        "SPEAKER_00": (
            NameOption("Maya", "roster", "possible", quote=""),
        )
    }
    llm = {
        "SPEAKER_00": NameOption(
            "Maya", "self_intro", "likely", quote="I'm Maya", source="llm"
        )
    }
    merged = merge_llm_options(det, llm)
    assert merged["SPEAKER_00"][0].source == "llm"


@pytest.mark.unit
def test_workspace_payload_includes_name_suggestions() -> None:
    controller = MagicMock()
    controller.cached_clip_status.return_value = MagicMock(status="miss", clip_id="c1")
    controller.ffmpeg_available.return_value = True
    payload = {
        "status_message": "ok",
        "roster": [{"display_name": "Maya", "mention_count": 2}],
        "by_speaker": {
            "SPEAKER_00": [
                {
                    "display_name": "Maya",
                    "basis": "self_intro",
                    "confidence": "strong",
                    "quote": "I'm Maya",
                    "label": "Maya — Self-introduction",
                }
            ]
        },
    }
    data = build_workspace_data(
        transcript_path="/tmp/t.json",
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[],
        controller=controller,
        name_suggestions=payload,
    )
    assert data["name_suggestions"]["by_speaker"]["SPEAKER_00"][0]["display_name"] == "Maya"


@pytest.mark.unit
def test_llm_pass_skips_thinking_model(monkeypatch) -> None:
    from types import SimpleNamespace

    from transcriptx.core.speaker_profiles.identify.suggestions.service import (
        _try_llm_assignments,
    )

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.runtime.require_ollama_analysis",
        lambda _cfg: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.runtime.resolve_llm_runtime",
        lambda **_k: SimpleNamespace(
            model="qwen3:8b",
            model_source="profile",
            max_output_tokens=2048,
            max_input_chars=48000,
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.suggestions.service.get_config",
        lambda: SimpleNamespace(llm=SimpleNamespace(enabled=True, provider="ollama")),
    )
    roster = (RosterPerson("Maya", "maya", 1, (), ""),)
    per, used, status, model, source = _try_llm_assignments(
        [{"speaker": "SPEAKER_00", "text": "I'm Maya."}],
        {"SPEAKER_00": ()},
        roster,
    )
    assert used is False
    assert model == "qwen3:8b"
    assert "JSON speaker naming" in status
    assert per == {"SPEAKER_00": ()}


@pytest.mark.unit
def test_llm_pass_uses_resolved_profile_model(monkeypatch) -> None:
    from types import SimpleNamespace

    from transcriptx.core.speaker_profiles.identify.suggestions.models import NameOption
    from transcriptx.core.speaker_profiles.identify.suggestions.service import (
        SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID,
        _try_llm_assignments,
    )

    seen: dict[str, str] = {}

    def fake_resolve(*, llm_cfg, effort, consumer_id):
        seen["consumer_id"] = consumer_id
        seen["effort"] = effort
        return SimpleNamespace(
            model="gemma3:4b",
            model_source="profile",
            max_output_tokens=512,
            max_input_chars=12000,
        )

    client = MagicMock()
    client.is_available.return_value = True

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.runtime.require_ollama_analysis",
        lambda _cfg: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.runtime.resolve_llm_runtime",
        fake_resolve,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.runtime.build_ollama_analysis_client",
        lambda **_k: client,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.suggestions.service.get_config",
        lambda: SimpleNamespace(
            llm=SimpleNamespace(
                enabled=True, provider="ollama", default_temperature=0.1
            )
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.suggestions.service.run_llm_assignments",
        lambda *_a, **_k: {
            "SPEAKER_00": NameOption(
                "Maya", "self_intro", "likely", quote="I'm Maya", source="llm"
            )
        },
    )
    roster = (RosterPerson("Maya", "maya", 1, (), ""),)
    per, used, status, model, source = _try_llm_assignments(
        [{"speaker": "SPEAKER_00", "text": "I'm Maya."}],
        {"SPEAKER_00": ()},
        roster,
    )
    assert seen["consumer_id"] == SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID
    assert used is True
    assert model == "gemma3:4b"
    assert source == "profile"
    assert per["SPEAKER_00"][0].source == "llm"
    assert "gemma3:4b" in status


@pytest.mark.unit
def test_suggestions_cache_roundtrip(tmp_path) -> None:
    result = NameSuggestionsResult(
        transcript_path="/tmp/t.json",
        managed_transcript_id="mt-1",
        transcript_fingerprint="abc",
        roster=(RosterPerson("Maya", "maya", 2, ("SPEAKER_00",), "I'm Maya"),),
        per_speaker={
            "SPEAKER_00": (
                NameOption("Maya", "self_intro", "strong", quote="I'm Maya"),
            )
        },
        status_message="ok",
        llm_used=False,
    )
    path = write_cached_suggestions(result, root=tmp_path)
    assert path is not None and path.is_file()
    loaded = load_cached_suggestions(
        "mt-1", transcript_fingerprint="abc", root=tmp_path
    )
    assert loaded is not None
    assert loaded.roster[0].display_name == "Maya"
    assert loaded.per_speaker["SPEAKER_00"][0].display_name == "Maya"
    stale = load_cached_suggestions(
        "mt-1", transcript_fingerprint="other", root=tmp_path
    )
    assert stale is None
