"""
Runtime interfaces and Docker-backed implementations for transcription.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from transcriptx.core.utils.paths import PROJECT_ROOT

# Container name from docker-compose.whisperx.yml
WHISPERX_CONTAINER_NAME = "transcriptx-whisperx"
COMPOSE_FILE = "docker-compose.whisperx.yml"


def _likely_inside_docker() -> bool:
    """True if this process is likely running inside a Docker container."""
    if Path("/.dockerenv").exists():
        return True
    if os.environ.get("TRANSCRIPTX_DATA_DIR") == "/data":
        return True
    return False


class ContainerRuntime(Protocol):
    def ensure_ready(self) -> bool: ...

    def exec(
        self,
        command: list[str],
        *,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess: ...

    def copy_out(
        self, *, container_path: str, host_path: Path, timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess: ...


_DOCKER_SOCKET = Path("/var/run/docker.sock")
_DOCKER_DOCS = "See docs/docker.md for setup and troubleshooting."


def get_docker_whisperx_status() -> tuple[str, str]:
    """
    Determine why WhisperX is not available for user-facing messages.

    Returns:
        Tuple of (status, user_message). status is one of:
        - "ready": WhisperX container is running.
        - "docker_unavailable": Docker is not installed or not running.
        - "container_not_running": Docker is available but WhisperX container is not running.
    """
    # Socket not mounted
    if not _DOCKER_SOCKET.exists():
        return (
            "docker_unavailable",
            "Docker socket not mounted. Mount it (e.g. -v /var/run/docker.sock:/var/run/docker.sock) "
            f"and ensure your process can access it. {_DOCKER_DOCS}",
        )
    # Socket mounted but permission denied
    if not os.access(str(_DOCKER_SOCKET), os.R_OK | os.W_OK):
        return (
            "docker_unavailable",
            "Docker socket is mounted but permission denied (check access / run as root). "
            f"{_DOCKER_DOCS}",
        )
    # Try docker info; distinguish CLI missing vs daemon unreachable
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except FileNotFoundError:
        return (
            "docker_unavailable",
            "Docker CLI not installed or not in PATH.",
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return (
            "docker_unavailable",
            "Docker daemon unreachable or not running. "
            f"{_DOCKER_DOCS}",
        )
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            f"name={WHISPERX_CONTAINER_NAME}",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if WHISPERX_CONTAINER_NAME not in (result.stdout or ""):
        return (
            "container_not_running",
            "WhisperX container is not running. Start it with:\n  docker compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx",
        )
    return ("ready", "")


def check_whisperx_compose_service() -> bool:
    """
    Check if the WhisperX Docker Compose container is running.

    Returns:
        bool: True if the container is running, False otherwise
    """
    status, _ = get_docker_whisperx_status()
    return status == "ready"


def check_container_responsive() -> bool:
    """
    Check if the WhisperX container is responsive by running a simple command.

    Returns:
        bool: True if the container responds, False otherwise
    """
    try:
        test_cmd = [
            "docker",
            "exec",
            WHISPERX_CONTAINER_NAME,
            "sh",
            "-c",
            "echo 'ok'",
        ]
        result = subprocess.run(
            test_cmd, capture_output=True, text=True, timeout=5, check=False
        )
        return result.returncode == 0 and "ok" in result.stdout
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return False


def start_whisperx_compose_service() -> bool:
    """
    Start the WhisperX Docker Compose service.

    Returns:
        bool: True if the service started successfully, False otherwise
    """
    try:
        # Check if Docker Compose is available
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            compose_cmd = "docker-compose"
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try docker compose (v2)
            try:
                subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                compose_cmd = "docker compose"
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False

        # Get the project root directory
        compose_file_path = PROJECT_ROOT / COMPOSE_FILE

        if not compose_file_path.exists():
            return False

        # Start the service using docker-compose
        if compose_cmd == "docker-compose":
            cmd = [
                "docker-compose",
                "-f",
                str(compose_file_path),
                "--profile",
                "whisperx",
                "up",
                "-d",
                "whisperx",
            ]
        else:
            cmd = [
                "docker",
                "compose",
                "-f",
                str(compose_file_path),
                "--profile",
                "whisperx",
                "up",
                "-d",
                "whisperx",
            ]

        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            import time

            time.sleep(2)  # Wait for container to be ready
            return True
        return False
    except Exception:
        return False


@dataclass
class DockerCliRuntime:
    container_name: str = WHISPERX_CONTAINER_NAME

    def ensure_ready(self) -> bool:
        if not check_whisperx_compose_service():
            return False
        return check_container_responsive()

    def exec(
        self,
        command: list[str],
        *,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )

    def copy_out(
        self, *, container_path: str, host_path: Path, timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        cmd = [
            "docker",
            "cp",
            f"{self.container_name}:{container_path}",
            str(host_path),
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )


@dataclass
class FakeRuntime:
    ensure_ready_result: bool = True
    exec_results: Optional[list[subprocess.CompletedProcess]] = None
    copy_results: Optional[list[subprocess.CompletedProcess]] = None

    def __post_init__(self) -> None:
        self.exec_calls: list[tuple[list[str], Optional[int], bool]] = []
        self.copy_calls: list[tuple[str, Path, Optional[int]]] = []
        if self.exec_results is None:
            self.exec_results = []
        if self.copy_results is None:
            self.copy_results = []

    def ensure_ready(self) -> bool:
        return self.ensure_ready_result

    def exec(
        self,
        command: list[str],
        *,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        self.exec_calls.append((command, timeout, check))
        if self.exec_results:
            return self.exec_results.pop(0)
        return subprocess.CompletedProcess(command, 0, "", "")

    def copy_out(
        self, *, container_path: str, host_path: Path, timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        self.copy_calls.append((container_path, host_path, timeout))
        if self.copy_results:
            return self.copy_results.pop(0)
        return subprocess.CompletedProcess(
            ["docker", "cp", container_path, str(host_path)], 0, "", ""
        )
