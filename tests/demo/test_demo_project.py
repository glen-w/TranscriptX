"""Demo pack validation and transactional install/remove."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.gui_acceptance.harness import isolate_workspace
from transcriptx.demo.pack_loader import load_and_validate_pack
from transcriptx.demo.service import (
    DemoStatusKind,
    install_demo_project,
    remove_demo_project,
    status_demo_project,
)


@pytest.fixture
def demo_ws(monkeypatch, tmp_path: Path):
    ws = isolate_workspace(monkeypatch, tmp_path)
    import transcriptx.core.utils.slug_manager as sm

    monkeypatch.setattr(sm, "INDEX_FILE", ws.outputs_dir / ".transcriptx_index.json")
    monkeypatch.setattr(sm, "OUTPUTS_DIR", ws.outputs_dir)
    return ws


def test_pack_validates() -> None:
    pack = load_and_validate_pack()
    assert pack.pack_id == "transcriptx.demo.base"
    assert len(pack.transcripts) == 3
    assert all(t.slug.startswith("demo__") for t in pack.transcripts)
    assert pack.provenance_text.strip()


def test_install_remove_roundtrip(demo_ws) -> None:
    assert status_demo_project().kind == DemoStatusKind.MISSING
    result = install_demo_project()
    assert result.ok, result.errors
    assert result.status == DemoStatusKind.INSTALLED
    assert status_demo_project().kind == DemoStatusKind.INSTALLED
    inv = result.inventory
    assert inv is not None
    assert len(inv["transcripts"]) == 3
    for tx in inv["transcripts"]:
        assert Path(tx["managed_path"]).exists()
        run = demo_ws.outputs_dir / tx["slug"] / "demo_base_install_v1"
        assert run.exists()
    # Idempotent
    again = install_demo_project()
    assert again.ok and again.status == DemoStatusKind.INSTALLED
    removed = remove_demo_project()
    assert removed.ok, removed.errors
    assert status_demo_project().kind == DemoStatusKind.MISSING
    for tx in inv["transcripts"]:
        assert not Path(tx["managed_path"]).exists()


def test_collision_blocks_install(demo_ws) -> None:
    first = install_demo_project()
    assert first.ok
    # Drop inventory but leave managed file → collision on reinstall after remove inventory only
    from transcriptx.demo import service as svc

    inv_path = svc.inventory_path()
    assert inv_path.exists()
    # Simulate foreign occupancy: remove inventory then try install while files remain
    # First properly remove then plant a colliding managed path.
    assert remove_demo_project().ok
    pack = load_and_validate_pack()
    occupied = demo_ws.transcripts_dir / pack.transcripts[0].basename
    occupied.write_text("{}", encoding="utf-8")
    blocked = install_demo_project()
    assert blocked.ok is False
    assert any("occupied" in e or "registered" in e for e in blocked.errors)
