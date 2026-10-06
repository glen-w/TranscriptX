"""Unit tests for copyable transcription command generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.services.transcription.command_gen import (
    CommandGenParams,
    TranscriptionTool,
    generate_preview_lines,
    generate_transcription_command,
)


@pytest.mark.unit
def test_whispermlx_single_quotes_spaces() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path="/Users/me/My Audio/meeting.mp3",
        output_dir="/Users/me/My Transcripts",
        diarize=True,
    )
    cmd = generate_transcription_command(params)
    assert "My Audio/meeting.mp3" in cmd.shell or "My\\ Audio" in cmd.shell
    assert "'/Users/me/My Audio/meeting.mp3'" in cmd.shell
    assert "'/Users/me/My Transcripts'" in cmd.shell
    assert "--diarize" in cmd.shell
    assert "subprocess" not in cmd.shell.lower()


@pytest.mark.unit
def test_whispermlx_folder_loop() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path="/audio/batch folder",
        output_dir="/out",
        audio_glob="*.wav",
        diarize=False,
    )
    cmd = generate_transcription_command(params)
    assert "folder loop" in cmd.title.lower() or "for f in" in cmd.shell
    assert "'/audio/batch folder'" in cmd.shell
    assert "*.wav" in cmd.shell
    assert "--diarize" not in cmd.shell


@pytest.mark.unit
def test_whispermlx_missing_flags() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/src with spaces",
        output_dir="/tx",
        dry_run=True,
        force=True,
        fuzzy_json_match=True,
        skip_serial=True,
        model="medium",
        language="de",
    )
    cmd = generate_transcription_command(params)
    assert "whispermlx-missing" in cmd.shell
    assert "--dry-run" in cmd.shell
    assert "--force" in cmd.shell
    assert "--fuzzy-json-match" in cmd.shell
    assert "--skip-serial" in cmd.shell
    assert "'/src with spaces'" in cmd.shell
    assert "--whisper-args" in cmd.shell
    assert "medium" in cmd.shell
    assert "de" in cmd.shell
    assert any("~/.local/bin" in note for note in cmd.notes)
    assert any("PATH" in note for note in cmd.notes)
    assert any("/opt/venv" in note for note in cmd.notes)


@pytest.mark.unit
def test_default_host_env_file_avoids_container_install_tree(tmp_path: Path) -> None:
    from transcriptx.services.transcription.command_gen import (
        default_host_env_file,
        default_host_script_ref,
        looks_like_container_install_path,
    )

    container_root = Path("/opt/venv/lib/python3.10")
    assert looks_like_container_install_path(container_root)
    assert default_host_env_file(container_root) == "whisperx.env"
    assert default_host_script_ref(container_root) == "scripts/whispermlx-missing.py"

    repo = tmp_path / "transcriptx"
    (repo / "scripts").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / "scripts" / "whispermlx-missing.py").write_text(
        "# stub\n", encoding="utf-8"
    )
    assert default_host_env_file(repo) == str(repo / "whisperx.env")
    assert default_host_script_ref(repo) == str(
        repo / "scripts" / "whispermlx-missing.py"
    )


@pytest.mark.unit
def test_whisperx_docker_recipe() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERX_DOCKER,
        input_path="/data/audio",
        output_dir="/data/out",
        device="cuda",
        compute_type="float16",
        diarize=True,
        min_speakers=2,
        max_speakers=8,
    )
    cmd = generate_transcription_command(params)
    assert "docker run" in cmd.shell
    assert "--device" in cmd.shell
    assert "cuda" in cmd.shell
    assert "--diarize" in cmd.shell
    assert "--min_speakers 2" in cmd.shell
    assert "--max_speakers 8" in cmd.shell
    assert "whisperx_json" in "\n".join(generate_preview_lines(params))
    assert "Import Transcript" in cmd.next_step


@pytest.mark.unit
def test_whisper_webui_docker_deploy() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPER_WEBUI_DOCKER,
        input_path="/unused",
        output_dir="/Users/me/My Outputs",
        model="medium",
        language="fr",
        diarize=True,
        device="cuda",
        docker_image="jhj0517/whisper-webui:v1.0.8-4def223",
        webui_port=7861,
        webui_clone_dir="$HOME/Whisper-WebUI",
        expected_output_format="srt_vtt",
    )
    cmd = generate_transcription_command(params)
    assert "Whisper-WebUI" in cmd.title or "whisper-webui" in cmd.shell.lower()
    assert "docker run" in cmd.shell
    assert "jhj0517/whisper-webui:v1.0.8-4def223" in cmd.shell
    assert "--gpus all" in cmd.shell
    assert "127.0.0.1:$PORT:7860" in cmd.shell or "127.0.0.1:$PORT" in cmd.shell
    assert "7861" in cmd.shell
    assert "'/Users/me/My Outputs'" in cmd.shell
    assert "git clone" in cmd.shell
    assert "127.0.0.1" in cmd.shell
    assert "medium" in cmd.shell
    assert "fr" in cmd.shell
    assert any("Apple Silicon" in n for n in cmd.notes)
    assert any(
        "does not own" in n.lower() or "interoperability" in n.lower()
        for n in cmd.notes
    )
    assert any("SRT" in n or "VTT" in n for n in cmd.notes)
    assert "srt_vtt" in "\n".join(generate_preview_lines(params))
    assert "Import Transcript" in cmd.next_step


@pytest.mark.unit
def test_whisper_webui_cpu_omits_gpus() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPER_WEBUI_DOCKER,
        input_path="/a",
        output_dir="/b",
        device="cpu",
        expected_output_format="srt_vtt",
    )
    cmd = generate_transcription_command(params)
    assert "--gpus" not in cmd.shell
    assert "127.0.0.1" in cmd.shell
    assert any("Apple Silicon" in n for n in cmd.notes)


@pytest.mark.unit
def test_expected_output_format_is_whisperx_json() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/a",
        output_dir="/b",
    )
    assert params.expected_output_format == "whisperx_json"
    cmd = generate_transcription_command(params)
    assert any("JSON" in n for n in cmd.notes)


@pytest.mark.unit
def test_whispermlx_uppercase_mp3_is_single_file() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path=r"C:\rec\meeting.MP3",
        output_dir=r"C:\out",
    )
    cmd = generate_transcription_command(params)
    assert "for f in" not in cmd.shell
    assert "meeting.MP3" in cmd.shell
    assert any("POSIX" in n for n in cmd.notes)


@pytest.mark.unit
def test_whispermlx_trailing_backslash_file_is_single() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path=r"C:\rec\meeting.mp3\\",
        output_dir=r"C:\out",
    )
    cmd = generate_transcription_command(params)
    assert "for f in" not in cmd.shell
    assert any("Git Bash" in n or "WSL" in n for n in cmd.notes)


@pytest.mark.unit
def test_whisperx_docker_notes_windows_mounts() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERX_DOCKER,
        input_path=r"C:\data\audio\\",
        output_dir=r"C:\data\out",
    )
    cmd = generate_transcription_command(params)
    assert "C:\\data\\audio" in cmd.shell or r"C:\data\audio" in cmd.shell
    assert cmd.shell.count("audio\\\\:/") == 0
    assert any("POSIX" in n for n in cmd.notes)
    assert any("C:\\" in n or "mount" in n.lower() for n in cmd.notes)


@pytest.mark.unit
def test_powershell_whisperx_docker_quotes_and_gpus() -> None:
    from transcriptx.services.transcription.command_gen import (
        generate_transcription_command_powershell,
    )

    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERX_DOCKER,
        input_path=r"C:\rec\My Audio",
        output_dir=r"C:\out",
        device="cuda",
        diarize=True,
    )
    cmd = generate_transcription_command_powershell(params)
    assert "PowerShell" in cmd.title
    assert "--gpus all" in cmd.shell
    assert "New-Item" in cmd.shell
    assert "'C:\\rec\\My Audio:/audio'" in cmd.shell or "My Audio" in cmd.shell
    assert any("PowerShell" in n for n in cmd.notes)
    assert "cmd.exe" in " ".join(cmd.notes)


@pytest.mark.unit
def test_powershell_whispermlx_missing_uses_python() -> None:
    from transcriptx.services.transcription.command_gen import (
        generate_transcription_command_powershell,
    )

    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path=r"C:\src",
        output_dir=r"C:\tx",
        dry_run=True,
    )
    cmd = generate_transcription_command_powershell(params)
    assert "python" in cmd.shell
    assert "whispermlx-missing.py" in cmd.shell
    assert "--dry-run" in cmd.shell
    assert "'C:\\src'" in cmd.shell or "C:\\src" in cmd.shell
