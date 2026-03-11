"""
Regression tests: prevent re-coupling to WhisperX or Docker orchestration.

Scans source under src/transcriptx for forbidden references (docker socket,
docker invocation strings, whisperx in core/cli). Excludes __pycache__ and
allowlisted modules (io format adapters). Also asserts Dockerfile and
docker-compose.yml do not install or mount Docker (analysis-only image).
"""

import os
import re

import pytest


def _collect_py_files(root: str, exclude_dirs: frozenset, allowlist: frozenset):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for f in filenames:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, root)
            if rel in allowlist:
                continue
            out.append(path)
    return out


def test_no_docker_socket_references():
    """No reference to Docker socket path in source."""
    root = os.path.join(os.path.dirname(__file__), "..", "..", "src", "transcriptx")
    exclude = frozenset({"__pycache__", ".mypy_cache", "vendored"})
    allowlist = frozenset()
    files = _collect_py_files(root, exclude, allowlist)
    bad = []
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if "/var/run/docker.sock" in line:
                    bad.append((path, i, line.strip()[:80]))
    assert not bad, f"Docker socket references found: {bad}"


def test_no_docker_invocation_strings():
    """No docker exec/cp/compose/run string literals in source (except doc/help text)."""
    root = os.path.join(os.path.dirname(__file__), "..", "..", "src", "transcriptx")
    exclude = frozenset({"__pycache__", ".mypy_cache", "vendored"})
    # User-facing help text that shows example docker run for users (no orchestration)
    allowlist = frozenset({"web/page_modules/audio_prep.py"})
    patterns = [
        "docker exec",
        "docker cp",
        "docker compose",
        "docker run",
    ]
    files = _collect_py_files(root, exclude, frozenset())
    bad = []
    for path in files:
        rel = os.path.relpath(path, root).replace("\\", "/")
        if rel in allowlist:
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            for pat in patterns:
                if pat in content:
                    bad.append((path, pat))
                    break
    assert not bad, f"Docker invocation strings found: {bad}"


def test_no_whisperx_in_core_or_cli():
    """No 'whisperx' in core/** or cli/** except allowlisted io adapters."""
    base = os.path.join(os.path.dirname(__file__), "..", "..", "src", "transcriptx")
    exclude = frozenset({"__pycache__", ".mypy_cache"})
    allowlist = frozenset(
        {
            "transcriptx/io/transcript_loader.py",
            "transcriptx/io/transcript_importer.py",
            "cli/main.py",
            "cli/transcript_file_commands.py",
        }
    )
    for sub in ("core", "cli"):
        root = os.path.join(base, sub)
        if not os.path.isdir(root):
            continue
        files = _collect_py_files(root, exclude, allowlist)
        for path in files:
            rel = os.path.relpath(path, base)
            if rel.replace("\\", "/") in allowlist:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if "whisperx" in line.lower():
                        bad_rel = os.path.relpath(path, base)
                        pytest.fail(
                            f"Found 'whisperx' in {bad_rel}:{i}: {line.strip()[:80]}"
                        )


def test_no_ghost_nouns_in_source():
    """No ghost nouns (docker socket, hf_token, diarised transcripts dir) in core/ and cli/."""
    base = os.path.join(os.path.dirname(__file__), "..", "..", "src", "transcriptx")
    exclude = frozenset({"__pycache__", ".mypy_cache"})
    patterns = [
        ("docker socket", re.IGNORECASE),
        ("diarised transcripts dir", re.IGNORECASE),
    ]
    for sub in ("core", "cli"):
        root = os.path.join(base, sub)
        if not os.path.isdir(root):
            continue
        files = _collect_py_files(root, exclude, frozenset())
        for path in files:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                for pat, flags in patterns:
                    if re.search(re.escape(pat), content, flags):
                        rel = os.path.relpath(path, base)
                        pytest.fail(f"Found '{pat}' in {rel}")
                if "hf_token" in content.lower():
                    rel = os.path.relpath(path, base)
                    pytest.fail(f"Found 'hf_token' in {rel}")


def test_dockerfile_no_docker_io():
    """Dockerfile must not install docker.io or docker-ce-cli (analysis-only image)."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    dockerfile_path = os.path.join(repo_root, "Dockerfile")
    if not os.path.isfile(dockerfile_path):
        pytest.skip("Dockerfile not found")
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()
    for forbidden in ("docker.io", "docker-ce-cli"):
        assert forbidden not in content, f"Dockerfile must not install {forbidden}"


def test_compose_no_socket_mount():
    """docker-compose.yml must not mount the Docker socket."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    compose_path = os.path.join(repo_root, "docker-compose.yml")
    if not os.path.isfile(compose_path):
        pytest.skip("docker-compose.yml not found")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert (
        "/var/run/docker.sock" not in content
    ), "docker-compose.yml must not mount the Docker socket (analysis-only image)"


def test_dockerfile_bakes_nltk_data():
    """Dockerfile must pre-download NLTK data for sentiment/understandability."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    dockerfile_path = os.path.join(repo_root, "Dockerfile")
    if not os.path.isfile(dockerfile_path):
        pytest.skip("Dockerfile not found")
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert (
        "nltk.download" in content
    ), "Dockerfile should bake NLTK data (vader_lexicon, punkt)"


def test_compose_has_cache_volume():
    """docker-compose.yml must define transcriptx_cache volume for CLI service."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    compose_path = os.path.join(repo_root, "docker-compose.yml")
    if not os.path.isfile(compose_path):
        pytest.skip("docker-compose.yml not found")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert (
        "transcriptx_cache" in content
    ), "docker-compose.yml should define transcriptx_cache volume"


def test_default_compose_downloads_enabled():
    """TRANSCRIPTX_DISABLE_DOWNLOADS in compose should default to 0 (allow downloads)."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    compose_path = os.path.join(repo_root, "docker-compose.yml")
    if not os.path.isfile(compose_path):
        pytest.skip("docker-compose.yml not found")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert (
        "TRANSCRIPTX_DISABLE_DOWNLOADS" in content and ":-0}" in content
    ), "transcriptx service should default DISABLE_DOWNLOADS to 0"
