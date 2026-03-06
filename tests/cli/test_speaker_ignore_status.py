import json
from pathlib import Path

from transcriptx.cli.speaker_utils import check_speaker_identification_status


def _write_transcript(path: Path, speakers: list[str], ignored: list[str]) -> None:
    segments = [
        {"speaker": speaker, "text": f"hello from {speaker}", "start": 0.0, "end": 1.0}
        for speaker in speakers
    ]
    payload = {"segments": segments, "ignored_speakers": ignored}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ignored_speakers_reduce_missing_ids(tmp_path: Path) -> None:
    transcript = tmp_path / "ignored.json"
    _write_transcript(transcript, ["SPEAKER_00", "SPEAKER_01"], ["SPEAKER_01"])

    status = check_speaker_identification_status(transcript)

    assert status.total_count == 2
    assert status.ignored_count == 1
    assert status.resolved_count == 1
    assert status.missing_ids == ["SPEAKER_00"]
    assert status.is_complete is False
    assert status.is_ok is False


def test_all_ignored_speakers_mark_complete(tmp_path: Path) -> None:
    transcript = tmp_path / "all_ignored.json"
    _write_transcript(
        transcript, ["SPEAKER_00", "SPEAKER_01"], ["SPEAKER_00", "SPEAKER_01"]
    )

    status = check_speaker_identification_status(transcript)

    assert status.total_count == 2
    assert status.ignored_count == 2
    assert status.resolved_count == 2
    assert status.missing_ids == []
    assert status.is_complete is True
    assert status.is_ok is True
