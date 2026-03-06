"""
Phase 0 safety net: contract tests for check_batch_speaker_gate and check_group_speaker_preflight.

Locks shared behavior (no identification needed -> PROCEED; force_non_interactive + enforce -> SKIP;
force_non_interactive + warn -> PROCEED) so extraction into _speaker_gate_for_paths does not change behavior.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from transcriptx.cli.speaker_utils import (
    SpeakerGateDecision,
    SpeakerIdStatus,
    check_batch_speaker_gate,
    check_group_speaker_preflight,
)
from transcriptx.core.utils.config.workflow import SpeakerGateConfig


def _complete_status() -> SpeakerIdStatus:
    return SpeakerIdStatus(
        is_ok=True,
        is_complete=True,
        ignored_count=0,
        named_count=1,
        resolved_count=1,
        total_count=1,
        segment_named_count=10,
        segment_total_count=10,
        missing_ids=[],
    )


def _incomplete_status() -> SpeakerIdStatus:
    return SpeakerIdStatus(
        is_ok=False,
        is_complete=False,
        ignored_count=0,
        named_count=0,
        resolved_count=0,
        total_count=1,
        segment_named_count=0,
        segment_total_count=10,
        missing_ids=["SPEAKER_00"],
    )


class TestCheckBatchSpeakerGateContract:
    """Contract tests for check_batch_speaker_gate."""

    def test_no_paths_need_identification_returns_proceed(self) -> None:
        """When no paths need identification, decision is PROCEED (no prompt)."""
        decision, needs, already, statuses = check_batch_speaker_gate([])
        assert decision == SpeakerGateDecision.PROCEED
        assert needs == []
        assert already == []
        assert statuses == {}

    def test_all_paths_already_identified_returns_proceed(self) -> None:
        """When all paths are already identified, decision is PROCEED."""
        with patch(
            "transcriptx.cli.speaker_utils.check_speaker_identification_status",
            return_value=_complete_status(),
        ):
            decision, needs, already, statuses = check_batch_speaker_gate(
                ["/some/path.json"]
            )
        assert decision == SpeakerGateDecision.PROCEED
        assert needs == []
        assert already == ["/some/path.json"]

    def test_force_non_interactive_enforce_returns_skip(self) -> None:
        """When force_non_interactive and mode is enforce, decision is SKIP."""
        config = SpeakerGateConfig(mode="enforce")
        mock_config = MagicMock()
        mock_config.workflow.speaker_gate = config

        with (
            patch(
                "transcriptx.cli.speaker_utils.check_speaker_identification_status",
                return_value=_incomplete_status(),
            ),
            patch("transcriptx.cli.speaker_utils.get_config", return_value=mock_config),
        ):
            decision, needs, already, statuses = check_batch_speaker_gate(
                ["/some/path.json"],
                force_non_interactive=True,
            )
        assert decision == SpeakerGateDecision.SKIP
        assert len(needs) == 1
        assert needs == ["/some/path.json"]

    def test_force_non_interactive_warn_returns_proceed(self) -> None:
        """When force_non_interactive and mode is warn, decision is PROCEED."""
        config = SpeakerGateConfig(mode="warn")
        mock_config = MagicMock()
        mock_config.workflow.speaker_gate = config

        with (
            patch(
                "transcriptx.cli.speaker_utils.check_speaker_identification_status",
                return_value=_incomplete_status(),
            ),
            patch("transcriptx.cli.speaker_utils.get_config", return_value=mock_config),
        ):
            decision, needs, already, statuses = check_batch_speaker_gate(
                ["/some/path.json"],
                force_non_interactive=True,
            )
        assert decision == SpeakerGateDecision.PROCEED
        assert len(needs) == 1


class TestCheckGroupSpeakerPreflightContract:
    """Contract tests for check_group_speaker_preflight."""

    def test_resolution_failure_returns_skip(self) -> None:
        """When member_transcript_ids cannot be resolved to paths, returns SKIP."""
        with patch(
            "transcriptx.cli.speaker_utils.resolve_transcript_paths",
            side_effect=ValueError("not found"),
        ):
            decision, needs, already, statuses = check_group_speaker_preflight([999])
        assert decision == SpeakerGateDecision.SKIP
        assert needs == []
        assert already == []
        assert statuses == {}

    def test_no_paths_need_identification_returns_proceed(self) -> None:
        """When all resolved paths are already identified, decision is PROCEED."""
        with (
            patch(
                "transcriptx.cli.speaker_utils.resolve_transcript_paths",
                return_value=[Path("/some/path.json")],
            ),
            patch(
                "transcriptx.cli.speaker_utils.check_speaker_identification_status",
                return_value=_complete_status(),
            ),
        ):
            decision, needs, already, statuses = check_group_speaker_preflight([1])
        assert decision == SpeakerGateDecision.PROCEED
        assert needs == []
        assert already == ["/some/path.json"]

    def test_force_non_interactive_enforce_returns_skip(self) -> None:
        """When force_non_interactive and mode is enforce, decision is SKIP."""
        config = SpeakerGateConfig(mode="enforce")
        mock_config = MagicMock()
        mock_config.workflow.speaker_gate = config

        with (
            patch(
                "transcriptx.cli.speaker_utils.resolve_transcript_paths",
                return_value=[Path("/some/path.json")],
            ),
            patch(
                "transcriptx.cli.speaker_utils.check_speaker_identification_status",
                return_value=_incomplete_status(),
            ),
            patch("transcriptx.cli.speaker_utils.get_config", return_value=mock_config),
        ):
            decision, needs, already, statuses = check_group_speaker_preflight(
                [1],
                force_non_interactive=True,
            )
        assert decision == SpeakerGateDecision.SKIP
        assert len(needs) == 1

    def test_force_non_interactive_warn_returns_proceed(self) -> None:
        """When force_non_interactive and mode is warn, decision is PROCEED."""
        config = SpeakerGateConfig(mode="warn")
        mock_config = MagicMock()
        mock_config.workflow.speaker_gate = config

        with (
            patch(
                "transcriptx.cli.speaker_utils.resolve_transcript_paths",
                return_value=[Path("/some/path.json")],
            ),
            patch(
                "transcriptx.cli.speaker_utils.check_speaker_identification_status",
                return_value=_incomplete_status(),
            ),
            patch("transcriptx.cli.speaker_utils.get_config", return_value=mock_config),
        ):
            decision, needs, already, statuses = check_group_speaker_preflight(
                [1],
                force_non_interactive=True,
            )
        assert decision == SpeakerGateDecision.PROCEED
        assert len(needs) == 1
