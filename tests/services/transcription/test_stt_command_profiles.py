"""Tests for STT command profile persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.services.transcription.command_gen import (
    CommandGenParams,
    TranscriptionTool,
)
from transcriptx.services.transcription.stt_command_profiles import (
    SttCommandProfileError,
    apply_params_to_session_state,
    command_gen_params_from_dict,
    command_gen_params_to_dict,
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)


@pytest.mark.unit
def test_command_gen_params_roundtrip_dict() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/Users/me/audio",
        output_dir="/Users/me/out",
        model="medium",
        language="de",
        diarize=False,
        dry_run=True,
        force=True,
        fuzzy_json_match=True,
    )
    restored = command_gen_params_from_dict(command_gen_params_to_dict(params))
    assert restored == params


@pytest.mark.unit
def test_from_dict_rejects_secrets() -> None:
    data = command_gen_params_to_dict(
        CommandGenParams(
            tool=TranscriptionTool.WHISPERMLX_SINGLE,
            input_path="/a",
            output_dir="/b",
        )
    )
    data["HF_TOKEN"] = "secret"
    with pytest.raises(SttCommandProfileError, match="secret"):
        command_gen_params_from_dict(data)


@pytest.mark.unit
def test_from_dict_rejects_unknown_schema() -> None:
    data = command_gen_params_to_dict(
        CommandGenParams(
            tool=TranscriptionTool.WHISPERMLX_SINGLE,
            input_path="/a",
            output_dir="/b",
        )
    )
    data["schema_version"] = 99
    with pytest.raises(SttCommandProfileError, match="schema_version"):
        command_gen_params_from_dict(data)


@pytest.mark.unit
def test_save_load_list_delete(tmp_path: Path) -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERX_DOCKER,
        input_path="/in",
        output_dir="/out",
        device="cuda",
        compute_type="float16",
        batch_size=8,
        min_speakers=2,
        max_speakers=4,
    )
    assert save_profile("gpu-meetings", params, profiles_dir=tmp_path)
    assert list_profiles(profiles_dir=tmp_path) == ["gpu-meetings"]
    loaded = load_profile("gpu-meetings", profiles_dir=tmp_path)
    assert loaded == params
    assert delete_profile("gpu-meetings", profiles_dir=tmp_path)
    assert list_profiles(profiles_dir=tmp_path) == []


@pytest.mark.unit
def test_apply_params_to_session_state() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/audio",
        output_dir="/json",
        model="large-v3",
        language="en",
        diarize=True,
    )
    labels = {
        TranscriptionTool.WHISPERMLX_MISSING: "whispermlx-missing (skip existing JSON)",
        TranscriptionTool.WHISPERMLX_SINGLE: "whispermlx (macOS host)",
        TranscriptionTool.WHISPERX_DOCKER: "WhisperX Docker (external recipe)",
        TranscriptionTool.WHISPER_WEBUI_DOCKER: "Whisper-WebUI Docker (Gradio)",
    }
    state: dict = {}
    apply_params_to_session_state(params, state, tool_labels=labels)
    assert state["tx_cmdgen_tool"] == labels[TranscriptionTool.WHISPERMLX_MISSING]
    assert state["tx_cmdgen_input"] == "/audio"
    assert state["tx_cmdgen_output"] == "/json"
    assert state["tx_cmdgen_model"] == "large-v3"
    assert state["tx_cmdgen_diarize"] is True


@pytest.mark.unit
def test_cannot_save_virtual_default(tmp_path: Path) -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path="/a",
        output_dir="/b",
    )
    assert not save_profile("default", params, profiles_dir=tmp_path)
