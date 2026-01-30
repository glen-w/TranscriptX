from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.transcription import _build_whisperx_run_spec  # type: ignore[import]
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR  # type: ignore[import]


@dataclass
class DummyTranscriptionConfig:
    model_name: str = "tiny"
    language: str = "en"
    compute_type: str = "float16"
    diarize: bool = False
    huggingface_token: str = "token123"


@dataclass
class DummyConfig:
    transcription: DummyTranscriptionConfig


def test_build_whisperx_run_spec_builds_expected_command() -> None:
    audio_path = Path("/tmp/audio.mp3")
    config = DummyConfig(transcription=DummyTranscriptionConfig())

    spec = _build_whisperx_run_spec(audio_path, config)

    assert spec.model == "tiny"
    assert spec.language == "en"
    assert spec.compute_type == "float32"
    assert spec.diarize is False
    assert spec.hf_token == "token123"
    assert spec.output_dir == Path(DIARISED_TRANSCRIPTS_DIR)
    assert spec.command[:4] == ["docker", "exec", "transcriptx-whisperx", "sh"]
    assert spec.command[4] == "-c"

    command_str = spec.command[5]
    assert "whisperx /data/input/audio.mp3" in command_str
    assert "--output_dir /tmp/whisperx_output" in command_str
    assert "--output_format json" in command_str
    assert "--model tiny" in command_str
    assert "--language en" in command_str
    assert "--compute_type float32" in command_str
    assert "--device cpu" in command_str
    assert "--hf_token token123" in command_str
    assert "--diarize" not in command_str
