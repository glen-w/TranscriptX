import subprocess

import transcriptx.core.transcription as transcription
import transcriptx.database.segment_storage as segment_storage


def test_transcription_no_db_calls(monkeypatch, tmp_path):
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake wav data")

    monkeypatch.setattr(transcription, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))
    expected_path = transcription.get_transcript_path_for_language(
        audio_file.stem, "auto"
    )
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_text(
        '{"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}'
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "", "")

    def fail_store(*args, **kwargs):
        raise AssertionError("DB store should not be called during transcription")

    monkeypatch.setattr(transcription.subprocess, "run", fake_run)
    monkeypatch.setattr(transcription, "check_container_responsive", lambda: True)
    monkeypatch.setattr(transcription.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        segment_storage, "store_transcript_segments_from_json", fail_store
    )

    result = transcription.run_whisperx_compose(audio_file)

    assert result == str(expected_path)
