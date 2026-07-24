"""Expanded plan-coverage tests for Guided mode + demo project."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.web.gui_acceptance.harness import isolate_workspace
from transcriptx.core.config.gui_support import COMMON_SETTINGS_SCHEMA
from transcriptx.demo.pack_loader import PackValidationError, load_and_validate_pack
from transcriptx.demo.service import (
    DemoStatusKind,
    _bounded_delete,
    compare_and_delete_slug,
    install_demo_project,
    refresh_demo_project,
    remove_demo_project,
    status_demo_project,
)
from transcriptx.web.navigation import pages_in_section
from transcriptx.web.presentation.guided_settings import GUIDED_SETTINGS_SCHEMA
from transcriptx.web.presentation.prefs import MODE_FULL, MODE_GUIDED
from transcriptx.web.presentation.visibility import (
    FULL_ONLY_PAGE_KEYS,
    page_visible_in_presentation,
)
from transcriptx.web.router import route_current_page
from transcriptx.web.state import PAGE_KEY


@pytest.fixture
def demo_ws(monkeypatch, tmp_path: Path):
    ws = isolate_workspace(monkeypatch, tmp_path)
    import transcriptx.core.utils.slug_manager as sm

    monkeypatch.setattr(sm, "INDEX_FILE", ws.outputs_dir / ".transcriptx_index.json")
    monkeypatch.setattr(sm, "OUTPUTS_DIR", ws.outputs_dir)
    return ws


def test_pages_in_section_tools_empty_after_audio_helpers() -> None:
    tools = pages_in_section("tools")
    keys = {p.key for p in tools}
    assert "Audio Prep" not in keys
    assert "Audio Merge" not in keys
    assert keys == set()


def test_guided_allowlist_narrower_than_common() -> None:
    guided = {f.key for f in GUIDED_SETTINGS_SCHEMA}
    common = {f.key for f in COMMON_SETTINGS_SCHEMA}
    assert guided
    assert guided < common or guided.isdisjoint(
        {k for k in common if "model" in k.lower() or "semantic" in k.lower()}
    )
    assert not any("model" in k.lower() for k in guided)
    assert not any("semantic" in k.lower() for k in guided)


def test_visibility_matrix_full_only_pages() -> None:
    for key in FULL_ONLY_PAGE_KEYS:
        assert page_visible_in_presentation(key, MODE_GUIDED) is False
        assert page_visible_in_presentation(key, MODE_FULL) is True


def test_router_full_only_guard_banner_only(monkeypatch) -> None:
    session = {PAGE_KEY: "Diagnostics"}
    banner = MagicMock()
    monkeypatch.setattr(
        "transcriptx.web.router.resolve_presentation_mode",
        lambda: MODE_GUIDED,
    )
    monkeypatch.setattr(
        "transcriptx.web.router.render_full_only_unlock_banner",
        banner,
    )
    # If guard fails, home would render — stub it to explode.
    monkeypatch.setattr(
        "transcriptx.web.router._render_home",
        lambda: (_ for _ in ()).throw(AssertionError("page body must not render")),
    )
    route_current_page(
        session,
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert session[PAGE_KEY] == "Diagnostics"
    banner.assert_called_once_with("Diagnostics")


def test_package_data_declares_demo_pack() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert '"transcriptx.demo.pack"' in text
    assert "transcripts/*.json" in text
    # Runtime resources (editable or installed) must resolve.
    pack = load_and_validate_pack()
    assert pack.transcripts


def test_symlink_escape_rejected(demo_ws, tmp_path: Path) -> None:
    roots = [demo_ws.transcripts_dir]
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = demo_ws.transcripts_dir / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    ok, msg = _bounded_delete(link, roots)
    assert ok is False
    assert "symlink" in msg or "escape" in msg
    assert outside.exists()


def test_compare_and_delete_skips_stale_identity(demo_ws) -> None:
    assert install_demo_project().ok
    inv = status_demo_project().inventory
    assert inv
    tx = inv["transcripts"][0]
    ok, msg = compare_and_delete_slug(
        slug=tx["slug"],
        identity="not-the-real-identity",
        source_path=tx["managed_path"],
    )
    assert ok is False
    assert "identity" in msg


def test_wrong_data_root_refuses_remove(demo_ws) -> None:
    assert install_demo_project().ok
    from transcriptx.demo import service as svc

    inv_path = svc.inventory_path()
    payload = json.loads(inv_path.read_text(encoding="utf-8"))
    payload["data_root"] = "/definitely/not/this/data/root"
    inv_path.write_text(json.dumps(payload), encoding="utf-8")
    result = remove_demo_project()
    assert result.ok is False
    assert result.status == DemoStatusKind.CORRUPT


def test_refresh_after_stale(demo_ws) -> None:
    assert install_demo_project().ok
    from transcriptx.demo import service as svc

    inv_path = svc.inventory_path()
    payload = json.loads(inv_path.read_text(encoding="utf-8"))
    payload["pack_hash"] = "stalehash"
    inv_path.write_text(json.dumps(payload), encoding="utf-8")
    assert status_demo_project().kind == DemoStatusKind.STALE
    result = refresh_demo_project()
    assert result.ok, result.errors
    assert status_demo_project().kind == DemoStatusKind.INSTALLED


def test_pack_validation_failure_blocks_mutation(monkeypatch, demo_ws) -> None:
    monkeypatch.setattr(
        "transcriptx.demo.service.load_and_validate_pack",
        lambda: (_ for _ in ()).throw(PackValidationError("boom")),
    )
    result = install_demo_project()
    assert result.ok is False
    assert result.status == DemoStatusKind.CORRUPT
    assert status_demo_project().kind == DemoStatusKind.MISSING


def test_same_members_group_conflict(demo_ws) -> None:
    from transcriptx.demo.service import _preflight_group_collision

    assert install_demo_project().ok
    inv = status_demo_project().inventory
    assert inv
    members = [t["managed_path"] for t in inv["transcripts"]]
    msg = _preflight_group_collision(members)
    assert msg is not None
    assert "already exists" in msg
    # Fresh install path refuses reuse rather than claiming the existing group.
    blocked = install_demo_project()
    assert blocked.ok  # idempotent when inventory present
    assert blocked.status == DemoStatusKind.INSTALLED
