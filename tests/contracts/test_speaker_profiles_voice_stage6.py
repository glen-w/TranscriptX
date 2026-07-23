"""Stage 6: VoiceAcceptanceOwner leave-unlinked writes nothing durable."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.voice.acceptance import VoiceAcceptanceOwner


def test_leave_unlinked_writes_no_decision(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    owner = VoiceAcceptanceOwner(root=root, state_dir=tmp_path / "state")
    (tmp_path / "state").mkdir()
    result = owner.leave_unlinked()
    assert result.decision_id is None
    decisions = root / "voice" / "decisions"
    assert not decisions.exists() or not any(decisions.glob("*.json"))
