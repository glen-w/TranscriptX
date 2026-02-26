import subprocess

import transcriptx.core.transcription as transcription  # type: ignore[import]
import transcriptx.core.utils.transcript_languages as transcript_languages  # type: ignore[import]
import transcriptx.database.segment_storage as segment_storage  # type: ignore[import]
from transcriptx.core.transcription_runtime import FakeRuntime  # type: ignore[import]


def test_transcription_no_db_calls(monkeypatch, tmp_path) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake wav data")

    monkeypatch.setattr(transcription, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(transcription, "RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setattr(transcript_languages, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))
    expected_path = transcript_languages.get_transcript_path_for_language(
        audio_file.stem, "auto"
    )
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_text(
        '{"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}'
    )

    def fail_store(*args, **kwargs):
        raise AssertionError("DB store should not be called during transcription")

    monkeypatch.setattr(
        transcription, "verify_model_availability", lambda *_: (True, None)
    )
    monkeypatch.setattr(transcription, "check_whisperx_compose_service", lambda: True)
    monkeypatch.setattr(transcription, "check_container_responsive", lambda: True)
    monkeypatch.setattr(transcription.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        segment_storage, "store_transcript_segments_from_json", fail_store
    )

    fake_runtime = FakeRuntime(
        exec_results=[
            subprocess.CompletedProcess(["verify-audio"], 0, "found\n", ""),
            subprocess.CompletedProcess(["whisperx"], 0, "", ""),
            subprocess.CompletedProcess(
                ["find-temp"], 0, "/tmp/whisperx_output/audio.json\n", ""
            ),
        ],
        copy_results=[subprocess.CompletedProcess(["docker", "cp"], 0, "", "")],
    )
    result = transcription.run_whisperx_compose(audio_file, runtime=fake_runtime)

    assert result == str(expected_path)


def test_transcription_retries_without_alignment_when_language_has_no_default_align_model(
    monkeypatch, tmp_path
) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake wav data")

    # Keep all filesystem effects in tmp_path for the test
    monkeypatch.setattr(transcription, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(transcription, "RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setattr(transcript_languages, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

    expected_path = transcript_languages.get_transcript_path_for_language(
        audio_file.stem, "auto"
    )
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_text('{"segments":[{"text":"Hello"}]}')

    # Avoid external environment dependencies
    monkeypatch.setattr(
        transcription, "verify_model_availability", lambda *_: (True, None)
    )
    monkeypatch.setattr(transcription, "check_whisperx_compose_service", lambda: True)
    monkeypatch.setattr(transcription, "check_container_responsive", lambda: True)
    monkeypatch.setattr(transcription.time, "sleep", lambda *_: None)

    # Runtime exec call order in run_whisperx_compose:
    # 1) verify audio file exists in container
    # 2) whisperx transcribe (fails: no default align-model)
    # 3) whisperx transcribe retry (--no_align) succeeds
    # 4) find json in temp output dir
    fake_runtime = FakeRuntime(
        exec_results=[
            subprocess.CompletedProcess(["verify-audio"], 0, "found\n", ""),
            subprocess.CompletedProcess(
                ["whisperx"],
                1,
                "",
                "ValueError: No default align-model for language: cy\n",
            ),
            subprocess.CompletedProcess(["whisperx"], 0, "", ""),
            subprocess.CompletedProcess(
                ["find-temp"], 0, "/tmp/whisperx_output/audio.json\n", ""
            ),
        ],
        copy_results=[subprocess.CompletedProcess(["docker", "cp"], 0, "", "")],
    )

    result = transcription.run_whisperx_compose(audio_file, runtime=fake_runtime)

    assert result == str(expected_path)

    # Assert retry happened and added --no_align
    exec_calls = fake_runtime.exec_calls
    assert len(exec_calls) >= 3
    retry_cmd = exec_calls[2][0]
    assert retry_cmd[-1].endswith("--no_align")
