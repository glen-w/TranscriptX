"""Persist / load Transcribe Audio command-gen presets (Theme K).

Uses ProfileManager under ``{PROFILES_DIR}/stt_commands/<name>.json``.
Never stores secrets (HF_TOKEN) — only form fields including an env file path.
"""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.profile_manager import ProfileManager
from transcriptx.services.transcription.command_gen import (
    DEFAULT_TRANSCRIPTION_MODEL,
    CommandGenParams,
    TranscriptionTool,
)

MODULE_ID = "stt_commands"
SCHEMA_VERSION = 1

_SECRET_KEYS = frozenset(
    {
        "hf_token",
        "HF_TOKEN",
        "token",
        "api_key",
        "openai_api_key",
        "OPENAI_API_KEY",
    }
)

_TOOL_VALUES = {t.value for t in TranscriptionTool}


class SttCommandProfileError(ValueError):
    """Invalid STT command profile payload."""


def _manager(profiles_dir=None) -> ProfileManager:
    return ProfileManager(profiles_dir=profiles_dir)


def list_profiles(*, profiles_dir=None) -> list[str]:
    return _manager(profiles_dir).list_profiles(MODULE_ID)


def delete_profile(name: str, *, profiles_dir=None) -> bool:
    return _manager(profiles_dir).delete_profile(MODULE_ID, name)


def command_gen_params_to_dict(params: CommandGenParams) -> dict[str, Any]:
    """Serialize CommandGenParams for profile storage (no secrets)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": params.tool.value,
        "input_path": params.input_path,
        "output_dir": params.output_dir,
        "model": params.model,
        "language": params.language,
        "diarize": bool(params.diarize),
        "env_file": params.env_file,
        "whispermlx_binary": params.whispermlx_binary,
        "audio_glob": params.audio_glob,
        "force": bool(params.force),
        "dry_run": bool(params.dry_run),
        "fuzzy_json_match": bool(params.fuzzy_json_match),
        "skip_serial": bool(params.skip_serial),
        "device": params.device,
        "compute_type": params.compute_type,
        "batch_size": int(params.batch_size),
        "min_speakers": params.min_speakers,
        "max_speakers": params.max_speakers,
        "docker_image": params.docker_image,
        "webui_port": int(params.webui_port),
        "webui_clone_dir": params.webui_clone_dir,
        "expected_output_format": params.expected_output_format,
    }


def command_gen_params_from_dict(data: dict[str, Any]) -> CommandGenParams:
    """Deserialize profile config into CommandGenParams."""
    if not isinstance(data, dict):
        raise SttCommandProfileError("Profile config must be an object")
    for key in _SECRET_KEYS:
        if key in data:
            raise SttCommandProfileError(f"Profile must not contain secret key {key!r}")
    version = data.get("schema_version", SCHEMA_VERSION)
    try:
        version_int = int(version)
    except (TypeError, ValueError) as exc:
        raise SttCommandProfileError("Invalid schema_version") from exc
    if version_int != SCHEMA_VERSION:
        raise SttCommandProfileError(
            f"Unsupported schema_version {version_int} (expected {SCHEMA_VERSION})"
        )

    tool_raw = data.get("tool", TranscriptionTool.WHISPERMLX_MISSING.value)
    tool_value = str(tool_raw)
    if tool_value not in _TOOL_VALUES:
        raise SttCommandProfileError(f"Unknown tool {tool_value!r}")

    min_speakers = data.get("min_speakers")
    max_speakers = data.get("max_speakers")
    if min_speakers is not None:
        min_speakers = int(min_speakers)
    if max_speakers is not None:
        max_speakers = int(max_speakers)

    return CommandGenParams(
        tool=TranscriptionTool(tool_value),
        input_path=str(data.get("input_path") or ""),
        output_dir=str(data.get("output_dir") or ""),
        model=str(data.get("model") or DEFAULT_TRANSCRIPTION_MODEL),
        language=str(data.get("language") or "en"),
        diarize=bool(data.get("diarize", True)),
        env_file=str(data.get("env_file") or "whisperx.env"),
        whispermlx_binary=str(data.get("whispermlx_binary") or "whispermlx"),
        audio_glob=str(data.get("audio_glob") or "*.mp3"),
        force=bool(data.get("force", False)),
        dry_run=bool(data.get("dry_run", False)),
        fuzzy_json_match=bool(data.get("fuzzy_json_match", False)),
        skip_serial=bool(data.get("skip_serial", False)),
        device=str(data.get("device") or "cpu"),
        compute_type=str(data.get("compute_type") or "float16"),
        batch_size=int(data.get("batch_size") or 16),
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        docker_image=str(data.get("docker_image") or "ghcr.io/m-bain/whisperx:latest"),
        webui_port=int(data.get("webui_port") or 7860),
        webui_clone_dir=str(data.get("webui_clone_dir") or "$HOME/Whisper-WebUI"),
        expected_output_format=str(
            data.get("expected_output_format") or "whisperx_json"
        ),
    )


def save_profile(
    name: str,
    params: CommandGenParams,
    *,
    description: str = "",
    overwrite: bool = True,
    profiles_dir=None,
) -> bool:
    """Save CommandGenParams as an stt_commands profile."""
    config = command_gen_params_to_dict(params)
    return _manager(profiles_dir).save_profile(
        MODULE_ID,
        name,
        config,
        description=description or f"STT command preset: {name}",
        overwrite=overwrite,
    )


def load_profile(name: str, *, profiles_dir=None) -> CommandGenParams:
    """Load a named profile into CommandGenParams."""
    payload = _manager(profiles_dir).load_profile(MODULE_ID, name)
    if payload is None:
        raise SttCommandProfileError(f"Profile {name!r} not found or invalid")
    config = payload.get("config")
    if not isinstance(config, dict):
        raise SttCommandProfileError(f"Profile {name!r} has no config object")
    return command_gen_params_from_dict(config)


def apply_params_to_session_state(
    params: CommandGenParams,
    session_state: dict[str, Any],
    *,
    tool_labels: dict[TranscriptionTool, str],
) -> None:
    """Write CommandGenParams into Transcribe Audio widget session keys."""
    session_state["tx_cmdgen_tool"] = tool_labels[params.tool]
    session_state["tx_cmdgen_input"] = params.input_path
    session_state["tx_cmdgen_output"] = params.output_dir
    session_state["tx_cmdgen_env"] = params.env_file
    session_state["tx_cmdgen_glob"] = params.audio_glob
    session_state["tx_cmdgen_model"] = params.model
    session_state["tx_cmdgen_language"] = params.language
    session_state["tx_cmdgen_diarize"] = params.diarize
    session_state["tx_cmdgen_dry"] = params.dry_run
    session_state["tx_cmdgen_force"] = params.force
    session_state["tx_cmdgen_fuzzy"] = params.fuzzy_json_match
    session_state["tx_cmdgen_skip_serial"] = params.skip_serial
    session_state["tx_cmdgen_bin"] = params.whispermlx_binary
    session_state["tx_cmdgen_device"] = params.device
    session_state["tx_cmdgen_compute"] = params.compute_type
    session_state["tx_cmdgen_batch"] = params.batch_size
    session_state["tx_cmdgen_speaker_bounds"] = (
        params.min_speakers is not None or params.max_speakers is not None
    )
    if params.min_speakers is not None:
        session_state["tx_cmdgen_min_spk"] = params.min_speakers
    if params.max_speakers is not None:
        session_state["tx_cmdgen_max_spk"] = params.max_speakers
    session_state["tx_cmdgen_webui_image"] = params.docker_image
    session_state["tx_cmdgen_webui_port"] = params.webui_port
    session_state["tx_cmdgen_webui_clone"] = params.webui_clone_dir
    session_state["tx_cmdgen_webui_device"] = params.device
