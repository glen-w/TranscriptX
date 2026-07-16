"""Unit tests for Corrections Studio generation input loading (0.3.9 split)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.core.corrections.models import CorrectionRule
from transcriptx.io.speaker_map_resolver import SpeakerMapState
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    load_generation_inputs,
)
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    FuzzySpeakerNameResolution,
)
from transcriptx.services.corrections_studio.schema import (
    StudioRule,
    StudioSessionDocument,
)


def _empty_fuzzy() -> FuzzySpeakerNameResolution:
    return FuzzySpeakerNameResolution(
        display_names_for_fuzzy=[],
        observed_named_speakers=[],
        sidecar_loaded=False,
        map_entries=0,
        load_failed=False,
    )


def _doc(*, rules: dict | None = None) -> StudioSessionDocument:
    return StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="hash",
        rules=rules or {},
    )


def _db_rule(d: dict) -> CorrectionRule:
    return CorrectionRule(
        id=d.get("id") or "r",
        type=d.get("type") or "phrase",
        wrong=d.get("wrong") or [],
        right=d.get("right") or "",
        scope=d.get("scope") or "global",
        confidence=float(d.get("confidence") or 0.0),
    )


@pytest.mark.unit
def test_load_generation_inputs_resolves_segment_speakers_when_sidecar_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.services.corrections_studio import (
        candidate_generation_inputs as mod,
    )

    segments = [{"speaker": "SPEAKER_00", "text": "hello"}]
    resolved = [{"speaker": "Alice", "text": "hello", "speaker_db_id": 7}]
    state = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice"},
        speaker_id_to_db_id={"SPEAKER_00": 7},
    )
    resolve_segments = MagicMock(return_value=resolved)

    class _Resolver:
        def resolve_segments(self, segs, speaker_state):
            return resolve_segments(segs, speaker_state)

    monkeypatch.setattr(mod, "SpeakerMapResolver", _Resolver)

    inp = load_generation_inputs(
        "/tmp/t.json",
        _doc(),
        get_config_fn=lambda: SimpleNamespace(
            analysis=SimpleNamespace(corrections=None)
        ),
        load_segments_fn=lambda _p: list(segments),
        load_memory_fn=lambda **_kw: SimpleNamespace(rules={}),
        resolve_fuzzy_fn=lambda *_a, **_k: _empty_fuzzy(),
        load_speaker_map_fn=lambda _p: state,
        db_rule_fn=_db_rule,
        compute_identity_hash_fn=lambda _segs: "tk",
    )

    resolve_segments.assert_called_once()
    assert inp.segments == resolved
    assert inp.transcript_key == "tk"
    assert inp.speaker_map_state is state
    assert inp.fuzzy_enabled is False
    assert inp.engine_rules == []


@pytest.mark.unit
def test_load_generation_inputs_skips_resolve_without_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.services.corrections_studio import (
        candidate_generation_inputs as mod,
    )

    segments = [{"speaker": "SPEAKER_00", "text": "hello"}]
    state = SpeakerMapState(has_sidecar=False, speaker_map={})
    resolve_mock = MagicMock()

    class _Resolver:
        def resolve_segments(self, *a, **k):
            return resolve_mock(*a, **k)

    monkeypatch.setattr(mod, "SpeakerMapResolver", _Resolver)

    inp = load_generation_inputs(
        "/tmp/t.json",
        _doc(),
        get_config_fn=lambda: SimpleNamespace(
            analysis=SimpleNamespace(corrections=None)
        ),
        load_segments_fn=lambda _p: list(segments),
        load_memory_fn=lambda **_kw: SimpleNamespace(rules={}),
        resolve_fuzzy_fn=lambda *_a, **_k: _empty_fuzzy(),
        load_speaker_map_fn=lambda _p: state,
        db_rule_fn=_db_rule,
        compute_identity_hash_fn=lambda _segs: "tk",
    )

    resolve_mock.assert_not_called()
    assert inp.segments == segments


@pytest.mark.unit
def test_load_generation_inputs_appends_studio_rules_and_skips_bad() -> None:
    good = StudioRule(
        rule_id="sr1",
        rule_type="acronym",
        wrong_variants=["foo"],
        replacement_text="FOO",
        confidence=0.8,
    )
    bad = StudioRule(
        rule_id="sr_bad",
        rule_type="acronym",
        wrong_variants=["x"],
        replacement_text="Y",
    )
    calls: list[dict] = []

    def _db_rule_fn(d: dict) -> CorrectionRule:
        calls.append(d)
        if d.get("id") == "sr_bad":
            raise ValueError("bad rule")
        return _db_rule(d)

    inp = load_generation_inputs(
        "/tmp/t.json",
        _doc(rules={"sr1": good, "sr_bad": bad}),
        get_config_fn=lambda: SimpleNamespace(
            analysis=SimpleNamespace(
                corrections=SimpleNamespace(
                    enable_fuzzy=True,
                    fuzzy_similarity_threshold=0.9,
                    consistency_similarity_threshold=0.4,
                )
            )
        ),
        load_segments_fn=lambda _p: [],
        load_memory_fn=lambda **_kw: SimpleNamespace(
            rules={
                "mem1": SimpleNamespace(
                    model_dump=lambda: {
                        "id": "mem1",
                        "type": "phrase",
                        "wrong": ["a"],
                        "right": "b",
                        "scope": "global",
                    }
                )
            }
        ),
        resolve_fuzzy_fn=lambda *_a, **_k: _empty_fuzzy(),
        load_speaker_map_fn=lambda _p: SpeakerMapState(has_sidecar=False),
        db_rule_fn=_db_rule_fn,
        compute_identity_hash_fn=lambda _segs: "tk",
    )

    assert [r.id for r in inp.engine_rules] == ["mem1", "sr1"]
    assert inp.fuzzy_enabled is True
    assert inp.fuzzy_threshold == 0.9
    assert inp.consistency_threshold == 0.4
    assert any(c.get("id") == "sr_bad" for c in calls)
