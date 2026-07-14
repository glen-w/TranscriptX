"""Release/packaging tests for packaging install smoke."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.release_only
def test_wheel_build_and_import_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(repo_root),
            "--no-deps",
            "-w",
            str(dist_dir),
        ],
        check=True,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wheels = sorted(dist_dir.glob("transcriptx-*.whl"))
    assert wheels, "Expected transcriptx wheel to be built"

    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(site_dir),
            str(wheels[-1]),
        ],
        check=True,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(site_dir) + os.pathsep + env.get("PYTHONPATH", "")

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import transcriptx; import transcriptx.web.__main__ as m; assert hasattr(transcriptx, '__version__'); assert callable(m.main)",
        ],
        check=True,
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from transcriptx.web.blocks.builtin import register_builtin_blocks; "
                "from transcriptx.web.layouts.store import LayoutProfileStore; "
                "register_builtin_blocks(); "
                "spec = LayoutProfileStore.load_layout('default'); "
                "assert spec.id == 'default'"
            ),
        ],
        check=True,
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
