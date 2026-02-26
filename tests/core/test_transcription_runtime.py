from pathlib import Path
from subprocess import CompletedProcess

from transcriptx.core.transcription_runtime import FakeRuntime  # type: ignore[import]


def test_fake_runtime_records_exec_and_returns_result() -> None:
    completed = CompletedProcess(["echo", "ok"], 0, "ok", "")
    runtime = FakeRuntime(exec_results=[completed])

    result = runtime.exec(["docker", "ps"], timeout=5, check=False)

    assert result.stdout == "ok"
    assert runtime.exec_calls == [(["docker", "ps"], 5, False)]


def test_fake_runtime_records_copy_out() -> None:
    runtime = FakeRuntime()
    target = Path("/tmp/transcript.json")

    result = runtime.copy_out(
        container_path="/tmp/output.json", host_path=target, timeout=30
    )

    assert result.returncode == 0
    assert runtime.copy_calls == [("/tmp/output.json", target, 30)]
