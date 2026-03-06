"""
Policy tests for speaker gate thresholds and exemplars.

Phase 0 safety net: tests for check_batch_speaker_gate and check_group_speaker_preflight
with mocked questionary and config lock shared behavior before deduplication refactor.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


from transcriptx.cli.speaker_utils import (  # type: ignore[import-untyped]
    SpeakerGateDecision,
    SpeakerIdStatus,
    check_batch_speaker_gate,
    check_group_speaker_preflight,
    _speaker_gate_choice_specs,
    _within_speaker_gate_threshold,
    get_unidentified_speaker_exemplars,
)
from transcriptx.core.utils.config.workflow import (  # type: ignore[import-untyped]
    SpeakerGateConfig,
    WorkflowConfig,
)


def _status(
    segment_total_count: int,
    segment_named_count: int,
    *,
    total_speakers: int = 1,
    named_speakers: int = 1,
) -> SpeakerIdStatus:
    ignored_count = 0
    resolved_count = named_speakers + ignored_count
    is_complete = total_speakers == 0 or resolved_count == total_speakers
    is_ok = is_complete
    missing_ids = [] if named_speakers == total_speakers else ["SPEAKER_00"]
    return SpeakerIdStatus(
        is_ok=is_ok,
        is_complete=is_complete,
        ignored_count=ignored_count,
        named_count=named_speakers,
        resolved_count=resolved_count,
        total_count=total_speakers,
        segment_named_count=segment_named_count,
        segment_total_count=segment_total_count,
        missing_ids=missing_ids,
    )


def test_threshold_absolute_boundaries() -> None:
    config = SpeakerGateConfig(threshold_value=3.0, threshold_type="absolute")
    assert _within_speaker_gate_threshold(_status(10, 7), config) is True
    assert _within_speaker_gate_threshold(_status(10, 6), config) is False


def test_threshold_percentage_boundaries() -> None:
    config = SpeakerGateConfig(threshold_value=10.0, threshold_type="percentage")
    assert _within_speaker_gate_threshold(_status(20, 18), config) is True
    assert _within_speaker_gate_threshold(_status(20, 17), config) is False


def test_threshold_total_zero_always_passes() -> None:
    config = SpeakerGateConfig(threshold_value=0.0, threshold_type="absolute")
    status = _status(0, 0, total_speakers=0, named_speakers=0)
    assert _within_speaker_gate_threshold(status, config) is True


def test_enforce_mode_choice_construction() -> None:
    enforce_choices = _speaker_gate_choice_specs("enforce", batch=False)
    enforce_decisions = [decision for _, decision in enforce_choices]
    assert SpeakerGateDecision.PROCEED not in enforce_decisions

    warn_choices = _speaker_gate_choice_specs("warn", batch=False)
    warn_decisions = [decision for _, decision in warn_choices]
    assert SpeakerGateDecision.PROCEED in warn_decisions


def test_exemplar_ranking_and_dedupe() -> None:
    segments = [
        {"speaker": "S1", "text": "Yeah."},
        {"speaker": "S1", "text": "I think we should adopt the new policy."},
        {"speaker": "S1", "text": "Yeah."},
        {"speaker": "S1", "text": "!!!"},
        {"speaker": "S1", "text": ""},
    ]
    exemplars = get_unidentified_speaker_exemplars(
        "unused.json",
        ["S1"],
        exemplar_count=2,
        segments=segments,
    )
    assert "S1" in exemplars
    assert exemplars["S1"][0].startswith("I think we should adopt")
    assert exemplars["S1"].count("Yeah.") <= 1
    assert "!!!" not in " ".join(exemplars["S1"])


def test_exemplars_disabled_short_circuit() -> None:
    segments = [{"speaker": "S1", "text": "Hello"}]
    exemplars = get_unidentified_speaker_exemplars(
        "unused.json",
        ["S1"],
        exemplar_count=0,
        segments=segments,
    )
    assert exemplars == {}


def _make_config(mode: str) -> WorkflowConfig:
    return WorkflowConfig(speaker_gate=SpeakerGateConfig(mode=mode))


def test_check_batch_speaker_gate_proceed_when_none_need_identification(
    tmp_path: Path,
) -> None:
    """When no paths need identification, decision is PROCEED."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
                ],
                "speaker_map": {"SPEAKER_00": "Alice"},
            }
        )
    )
    decision, needs, already, statuses = check_batch_speaker_gate([str(transcript)])
    assert decision == SpeakerGateDecision.PROCEED
    assert len(needs) == 0
    assert len(already) == 1


def test_check_batch_speaker_gate_force_non_interactive_enforce_returns_skip(
    tmp_path: Path,
) -> None:
    """When force_non_interactive and mode is enforce, decision is SKIP."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    },
                ],
            }
        )
    )
    with patch(
        "transcriptx.cli.speaker_utils.get_config",
        return_value=MagicMock(workflow=_make_config("enforce")),
    ):
        decision, needs, already, statuses = check_batch_speaker_gate(
            [str(transcript)], force_non_interactive=True
        )
    assert decision == SpeakerGateDecision.SKIP
    assert len(needs) == 1


def test_check_batch_speaker_gate_force_non_interactive_warn_returns_proceed(
    tmp_path: Path,
) -> None:
    """When force_non_interactive and mode is warn, decision is PROCEED."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    },
                ],
            }
        )
    )
    with patch(
        "transcriptx.cli.speaker_utils.get_config",
        return_value=MagicMock(workflow=_make_config("warn")),
    ):
        decision, needs, already, statuses = check_batch_speaker_gate(
            [str(transcript)], force_non_interactive=True
        )
    assert decision == SpeakerGateDecision.PROCEED
    assert len(needs) == 1


def test_check_group_speaker_preflight_force_non_interactive_enforce_returns_skip(
    tmp_path: Path,
) -> None:
    """When force_non_interactive and mode is enforce, group preflight returns SKIP."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0},
                ],
            }
        )
    )
    with (
        patch(
            "transcriptx.cli.speaker_utils.resolve_transcript_paths",
            return_value=[transcript],
        ),
        patch(
            "transcriptx.cli.speaker_utils.get_config",
            return_value=MagicMock(workflow=_make_config("enforce")),
        ),
    ):
        decision, needs, already, statuses = check_group_speaker_preflight(
            [1], force_non_interactive=True
        )
    assert decision == SpeakerGateDecision.SKIP
    assert len(needs) == 1
