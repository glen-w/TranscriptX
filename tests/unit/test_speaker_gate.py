"""Unit tests for turn-taking speaker counting and the speaker-count gate.

Default: all modules require human-named speakers (including former
turn-taking modules). When ``allow_unnamed_speakers`` is True, the gate
uses turn-taking counts so diarized labels (``SPEAKER_00``) suffice.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.utils.speaker_extraction import count_turn_taking_speakers
from transcriptx.core.pipeline.dag_pipeline_run import (
    gating_turn_taking_speaker_count,
    speaker_gate_skip_reason,
)
from transcriptx.core.pipeline.module_registry import get_module_info
from transcriptx.utils.text_utils import (
    get_pipeline_allow_unnamed_speakers,
    is_analysis_speaker_label,
    is_eligible_named_speaker,
    reset_pipeline_allow_unnamed_speakers,
    set_pipeline_allow_unnamed_speakers,
)


def _mod(
    *,
    gate_on_turn_taking_speakers: bool = False,
    requires_multiple_speakers: bool = False,
    min_named_speakers: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        gate_on_turn_taking_speakers=gate_on_turn_taking_speakers,
        requires_multiple_speakers=requires_multiple_speakers,
        min_named_speakers=min_named_speakers,
    )


# --- count_turn_taking_speakers -------------------------------------------


@pytest.mark.unit
def test_count_turn_taking_counts_diarized_labels() -> None:
    segs = [
        {"speaker": "SPEAKER_00", "text": "a"},
        {"speaker": "SPEAKER_01", "text": "b"},
        {"speaker": "SPEAKER_00", "text": "c"},
    ]
    assert count_turn_taking_speakers(segs) == 2


@pytest.mark.unit
def test_count_turn_taking_counts_named_speakers() -> None:
    segs = [{"speaker": "Alice", "text": "a"}, {"speaker": "Bob", "text": "b"}]
    assert count_turn_taking_speakers(segs) == 2


@pytest.mark.unit
def test_count_turn_taking_excludes_unknown_placeholders() -> None:
    segs = [
        {"speaker": "Unknown", "text": "a"},
        {"speaker": "Unidentified Speaker", "text": "b"},
        {"speaker": None, "text": "c"},
        {"text": "no speaker key"},
    ]
    assert count_turn_taking_speakers(segs) == 0


@pytest.mark.unit
def test_count_turn_taking_groups_by_db_id_when_present() -> None:
    # Same db_id with differing label text should collapse to one speaker.
    segs = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "a"},
        {"speaker": "Alice (1)", "speaker_db_id": 1, "text": "b"},
        {"speaker": "Bob", "speaker_db_id": 2, "text": "c"},
    ]
    assert count_turn_taking_speakers(segs) == 2


@pytest.mark.unit
def test_count_turn_taking_respects_ignored_ids() -> None:
    segs = [
        {"speaker": "SPEAKER_00", "text": "a"},
        {"speaker": "SPEAKER_01", "text": "b"},
    ]
    assert count_turn_taking_speakers(segs, ignored_speaker_ids={"SPEAKER_01"}) == 1


# --- gating_turn_taking_speaker_count -------------------------------------


@pytest.mark.unit
def test_gating_turn_taking_count_none_when_no_context() -> None:
    assert gating_turn_taking_speaker_count(None) is None


@pytest.mark.unit
def test_gating_turn_taking_count_from_context_segments() -> None:
    ctx = SimpleNamespace(
        get_segments=lambda: [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ]
    )
    assert gating_turn_taking_speaker_count(ctx) == 2


@pytest.mark.unit
def test_gating_turn_taking_count_fails_open_on_error() -> None:
    def _boom():
        raise RuntimeError("no segments")

    ctx = SimpleNamespace(get_segments=_boom)
    assert gating_turn_taking_speaker_count(ctx) is None


# --- speaker_gate_skip_reason (default: named required) -------------------


@pytest.mark.unit
def test_gate_default_skips_diarized_only_transcript() -> None:
    # Former turn-taking modules now require named speakers by default.
    info = _mod(min_named_speakers=1)
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=2,
        allow_unnamed_speakers=False,
    )
    assert reason == "requires at least 1 named speakers"


@pytest.mark.unit
def test_gate_default_multi_speaker_skips_without_named() -> None:
    info = _mod(requires_multiple_speakers=True)
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=2,
        allow_unnamed_speakers=False,
    )
    assert reason == "requires at least 2 named speakers"


@pytest.mark.unit
def test_gate_default_runs_with_named_speakers() -> None:
    info = _mod(min_named_speakers=1)
    assert (
        speaker_gate_skip_reason(
            info,
            named_speaker_count=1,
            turn_taking_speaker_count=2,
            allow_unnamed_speakers=False,
        )
        is None
    )


# --- speaker_gate_skip_reason (ungated) -----------------------------------


@pytest.mark.unit
def test_gate_ungated_runs_on_diarized_two_speakers() -> None:
    info = _mod(min_named_speakers=1)
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=2,
        allow_unnamed_speakers=True,
    )
    assert reason is None


@pytest.mark.unit
def test_gate_ungated_multi_speaker_runs_on_two_diarized() -> None:
    info = _mod(requires_multiple_speakers=True)
    assert (
        speaker_gate_skip_reason(
            info,
            named_speaker_count=0,
            turn_taking_speaker_count=2,
            allow_unnamed_speakers=True,
        )
        is None
    )


@pytest.mark.unit
def test_gate_ungated_multi_speaker_skips_single_speaker() -> None:
    info = _mod(requires_multiple_speakers=True)
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=1,
        allow_unnamed_speakers=True,
    )
    assert reason == "requires at least 2 speakers"


@pytest.mark.unit
def test_gate_fails_open_when_count_is_none() -> None:
    info = _mod(requires_multiple_speakers=True)
    assert (
        speaker_gate_skip_reason(
            info,
            named_speaker_count=None,
            turn_taking_speaker_count=None,
            allow_unnamed_speakers=True,
        )
        is None
    )


# --- eligibility helpers --------------------------------------------------


@pytest.mark.unit
def test_analysis_speaker_label_respects_allow_unnamed() -> None:
    assert is_analysis_speaker_label("SPEAKER_00", allow_unnamed=False) is False
    assert is_analysis_speaker_label("SPEAKER_00", allow_unnamed=True) is True
    assert is_analysis_speaker_label("Alice", allow_unnamed=False) is True


@pytest.mark.unit
def test_eligible_named_speaker_respects_pipeline_contextvar() -> None:
    assert is_eligible_named_speaker("SPEAKER_00", "SPEAKER_00") is False
    token = set_pipeline_allow_unnamed_speakers(True)
    try:
        assert get_pipeline_allow_unnamed_speakers() is True
        assert is_eligible_named_speaker("SPEAKER_00", "SPEAKER_00") is True
        assert is_analysis_speaker_label("SPEAKER_00") is True
    finally:
        reset_pipeline_allow_unnamed_speakers(token)
    assert is_eligible_named_speaker("SPEAKER_00", "SPEAKER_00") is False


# --- registry wiring ------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_name",
    [
        "echoes",
        "understandability",
        "lexical_diversity",
        "politeness",
        "epistemic_markers",
    ],
)
def test_former_turn_taking_modules_no_longer_opt_in(module_name: str) -> None:
    info = get_module_info(module_name)
    assert info is not None
    assert info.gate_on_turn_taking_speakers is False


@pytest.mark.unit
@pytest.mark.parametrize("module_name", ["stats", "sentiment", "echoes"])
def test_modules_require_named_speakers_by_default(module_name: str) -> None:
    info = get_module_info(module_name)
    assert info is not None
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=2,
        allow_unnamed_speakers=False,
    )
    assert reason is not None
    assert "named speakers" in reason
