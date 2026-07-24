"""Light coverage for 0.9.5 hosted-docs + harden-scaffold tooling."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release"


def _load(name: str):
    path = RELEASE / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_hygiene_strict_subset_root_and_banners_passes() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RELEASE / "repo_hygiene_audit.py"),
            "--strict",
            "--checks",
            "root_md,archive_banners",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Summary: 0 warning(s)" in proc.stdout


@pytest.mark.unit
def test_hygiene_unknown_check_id_fails() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RELEASE / "repo_hygiene_audit.py"),
            "--checks",
            "not_a_real_check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "unknown --checks" in (proc.stderr + proc.stdout)


@pytest.mark.unit
def test_hygiene_no_live_owner_absolute_paths() -> None:
    mod = _load("repo_hygiene_audit.py")
    live = [w for w in mod.check_owner_paths() if w.startswith("live ")]
    assert live == [], live


@pytest.mark.unit
def test_regen_module_docs_match_tracked_catalog_and_scaffold() -> None:
    """Drift gate: tracked generated docs must match registry renderer output."""
    mod = _load("regen_module_docs.py")
    defs = mod.build_all_module_definitions([])
    assert set(defs) == set(mod.MODULE_REGISTRY_ORDER)

    expected_modules = mod.render_modules_md(defs)
    expected_scaffold = mod.render_audit_scaffold(defs)
    actual_modules = mod.MODULES_MD.read_text(encoding="utf-8")
    actual_scaffold = mod.AUDIT_SCAFFOLD.read_text(encoding="utf-8")

    assert actual_modules == expected_modules
    assert actual_scaffold == expected_scaffold
    assert "semantic_similarity_advanced" not in actual_modules
    assert actual_modules.count("| semantic_similarity |") == 1
    for mid in mod.MODULE_REGISTRY_ORDER:
        assert f"| {mid} |" in actual_modules
        assert f"`{mid}`" in actual_scaffold


@pytest.mark.unit
def test_sphinx_scaffold_files_and_wiring() -> None:
    assert (ROOT / "docs" / "conf.py").is_file()
    assert (ROOT / "docs" / "index.md").is_file()
    assert (ROOT / "docs" / "requirements.txt").is_file()
    assert (ROOT / ".readthedocs.yml").is_file()
    assert (RELEASE / "build_docs.sh").is_file()

    conf = (ROOT / "docs" / "conf.py").read_text(encoding="utf-8")
    assert "myst_parser" in conf
    assert 'html_theme = "furo"' in conf

    rtd = (ROOT / ".readthedocs.yml").read_text(encoding="utf-8")
    assert "configuration: docs/conf.py" in rtd
    assert "docs" in rtd  # extra_requirements / path

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "scripts/release/build_docs.sh" in makefile
    assert "scripts/release/regen_module_docs.py" in makefile

    # Keep RTD hostname denylisted until an intentional project URL exists.
    stale = (RELEASE / "stale_refs.sh").read_text(encoding="utf-8")
    assert re.search(r"readthedocs\\.io", stale)


@pytest.mark.unit
def test_trust_draft_matrix_covers_builtin_profile_licences() -> None:
    trust = (ROOT / "docs" / "dev" / "trust_privacy_model_governance_1_0.md").read_text(
        encoding="utf-8"
    )
    assert "Apache-2.0" in trust
    assert "MIT" in trust
    assert "contextual_hartmann_distilroberta_v1" in trust
    assert "fine_grained_samlowe_go_emotions_v1" in trust
    assert "j-hartmann/emotion-english-distilroberta-base" in trust
    assert "SamLowe/roberta-base-go_emotions" in trust


@pytest.mark.unit
def test_sphinx_html_build_when_docs_extra_installed(tmp_path: Path) -> None:
    """Optional smoke: only when Sphinx from .[docs] is importable."""
    sphinx = pytest.importorskip("sphinx")
    _ = sphinx  # silence unused if importorskip returns module
    out = tmp_path / "html"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-q",
            str(ROOT / "docs"),
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (out / "index.html").is_file()
