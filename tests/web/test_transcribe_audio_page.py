"""Smoke tests for Transcribe Audio page."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions


@pytest.mark.unit
def test_transcribe_audio_page_callable():
    from transcriptx.web.page_modules.transcribe_audio import (
        render_transcribe_audio_page,
    )

    assert callable(render_transcribe_audio_page)


@pytest.mark.unit
def test_transcribe_audio_page_is_instruction_only():
    import transcriptx.web.page_modules.transcribe_audio as page

    source = Path(page.__file__).read_text(encoding="utf-8")
    assert "whispermlx-missing" in source
    assert "~/.local/bin" in source
    assert "on PATH" in source
    assert "python3 scripts/whispermlx-missing.py" in source
    assert "Import Transcript" in source
    assert "generate_transcription_command" in source
    assert "TRANSCRIPTION_MODEL_OPTIONS" in source
    assert "st.selectbox" in source
    assert 'st.text_input("Model"' not in source
    assert "st.file_uploader" not in source
    assert "TranscriptionController" not in source
    assert "subprocess" not in source
    assert "Popen" not in source
    assert "default_host_env_file" in source
    assert "looks_like_container_install_path" in source
    assert "/opt/venv" in source
    assert "Env file (host)" in source


@pytest.mark.unit
def test_transcribe_audio_page_env_default_is_host_safe():
    import transcriptx.web.page_modules.transcribe_audio as page

    assert not page.looks_like_container_install_path(page._ENV_FILE_DEFAULT)
    assert page._ENV_FILE_DEFAULT.endswith("whisperx.env")
    assert "/opt/venv/" not in page._SCRIPT_REF.replace("\\", "/")


@pytest.mark.unit
def test_transcription_model_options_include_default():
    from transcriptx.services.transcription.command_gen import (
        DEFAULT_TRANSCRIPTION_MODEL,
        TRANSCRIPTION_MODEL_OPTIONS,
    )

    assert DEFAULT_TRANSCRIPTION_MODEL == "large-v3"
    assert DEFAULT_TRANSCRIPTION_MODEL in TRANSCRIPTION_MODEL_OPTIONS
    assert "large-v3-turbo" in TRANSCRIPTION_MODEL_OPTIONS
    assert "tiny" in TRANSCRIPTION_MODEL_OPTIONS


@pytest.mark.unit
def test_transcribe_audio_page_does_not_execute_shell():
    import transcriptx.web.page_modules.transcribe_audio as page

    source = Path(page.__file__).read_text(encoding="utf-8")
    for forbidden in ("os.system", "subprocess.", "shell=True"):
        assert forbidden not in source


@pytest.mark.unit
def test_providers_include_whispermlx_only():
    from transcriptx.services.transcription.registry import get_transcription_providers

    ids = {p.provider_id for p in get_transcription_providers()}
    assert "whispermlx" in ids
    assert "whisperx_docker" not in ids


@pytest.mark.unit
def test_whisperx_docker_provider_file_still_unavailable():
    from transcriptx.services.transcription.whisperx_docker_provider import (
        WhisperXDockerProvider,
    )

    provider = WhisperXDockerProvider()
    options = TranscriptionOptions(
        provider_id="whisperx_docker",
        model="large-v3",
        language="en",
        diarize=False,
    )
    availability = provider.is_available(options)
    assert not availability.available
