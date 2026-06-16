"""Unit tests for turn-taking speaker counting and the speaker-count gate.

Covers the gate path that lets diarization-only modules (echoes,
understandability) run on transcripts whose speakers are unnamed
(``SPEAKER_00`` etc.) while still skipping single-speaker transcripts.
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


def _mod(
    *,
    gate_on_turn_taking_speakers: bool,
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


# --- speaker_gate_skip_reason ---------------------------------------------


@pytest.mark.unit
def test_gate_turn_taking_module_runs_on_diarized_two_speakers() -> None:
    # understandability-like: turn-taking, min 1
    info = _mod(gate_on_turn_taking_speakers=True, min_named_speakers=1)
    reason = speaker_gate_skip_reason(
        info, named_speaker_count=0, turn_taking_speaker_count=2
    )
    assert reason is None


@pytest.mark.unit
def test_gate_turn_taking_multi_speaker_module_runs_on_two_diarized() -> None:
    # echoes-like: turn-taking + requires_multiple_speakers (min 2)
    info = _mod(
        gate_on_turn_taking_speakers=True,
        requires_multiple_speakers=True,
    )
    assert (
        speaker_gate_skip_reason(
            info, named_speaker_count=0, turn_taking_speaker_count=2
        )
        is None
    )


@pytest.mark.unit
def test_gate_turn_taking_multi_speaker_module_skips_single_speaker() -> None:
    info = _mod(
        gate_on_turn_taking_speakers=True,
        requires_multiple_speakers=True,
    )
    reason = speaker_gate_skip_reason(
        info, named_speaker_count=0, turn_taking_speaker_count=1
    )
    assert reason == "requires at least 2 speakers"


@pytest.mark.unit
def test_gate_named_module_still_uses_named_count() -> None:
    # A non-turn-taking module is unaffected: gated on named count.
    info = _mod(gate_on_turn_taking_speakers=False, min_named_speakers=1)
    # Plenty of diarized speakers, but zero named -> skipped.
    reason = speaker_gate_skip_reason(
        info, named_speaker_count=0, turn_taking_speaker_count=5
    )
    assert reason == "requires at least 1 named speakers"


@pytest.mark.unit
def test_gate_fails_open_when_count_is_none() -> None:
    info = _mod(gate_on_turn_taking_speakers=True, requires_multiple_speakers=True)
    assert (
        speaker_gate_skip_reason(
            info, named_speaker_count=None, turn_taking_speaker_count=None
        )
        is None
    )


# --- registry wiring ------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("module_name", ["echoes", "understandability"])
def test_diarization_modules_opt_into_turn_taking_gate(module_name: str) -> None:
    info = get_module_info(module_name)
    assert info is not None
    assert info.gate_on_turn_taking_speakers is True


@pytest.mark.unit
@pytest.mark.parametrize("module_name", ["stats", "sentiment"])
def test_named_modules_do_not_opt_into_turn_taking_gate(module_name: str) -> None:
    info = get_module_info(module_name)
    assert info is not None
    assert info.gate_on_turn_taking_speakers is False
