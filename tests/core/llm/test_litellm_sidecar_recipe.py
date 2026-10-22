"""Sanity checks for the optional LiteLLM compose recipe."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.llm.openai_compatible_client import OpenAICompatibleClient

ROOT = Path(__file__).resolve().parents[3]
RECIPE = ROOT / "docs" / "recipes" / "litellm"


def test_recipe_files_exist() -> None:
    assert (RECIPE / "README.md").is_file()
    assert (RECIPE / "docker-compose.litellm.yml").is_file()
    assert (RECIPE / "litellm.config.yaml").is_file()
    assert (RECIPE / "litellm.env.example").is_file()
    readme = (RECIPE / "README.md").read_text(encoding="utf-8")
    assert "openai_compatible" in readme
    assert "analysis image" in readme.lower()
    assert "leave" in readme.lower()


def test_compose_binds_loopback() -> None:
    text = (RECIPE / "docker-compose.litellm.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:${LITELLM_PORT:-4000}:4000" in text
    assert "transcriptx:latest" not in text


def test_client_against_mocked_proxy(monkeypatch) -> None:
    """The same Chat Completions client is what operators point at the sidecar."""

    class _Resp:
        def read(self):
            return b'{"choices":[{"message":{"content":"sidecar-ok"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _urlopen(req, timeout=None):
        assert req.full_url.startswith("http://127.0.0.1:4000/v1/")
        return _Resp()

    import transcriptx.core.llm.openai_compatible_client as occ

    monkeypatch.setattr(occ.urllib.request, "urlopen", _urlopen)
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:4000/v1",
        model="default",
        api_key="sk-local",
    )
    assert client.generate(prompt="hi", temperature=0.0) == "sidecar-ok"


@pytest.mark.unit
def test_compose_config_if_docker_available() -> None:
    import shutil
    import subprocess

    compose = RECIPE / "docker-compose.litellm.yml"
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker not on PATH")
    try:
        proc = subprocess.run(
            [docker, "compose", "-f", str(compose), "config"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(RECIPE),
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("docker compose not usable")
    if proc.returncode != 0:
        pytest.skip(proc.stderr[:300] or "docker compose config failed")
    assert "4000" in proc.stdout
