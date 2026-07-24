"""Demo pack validation edge coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.demo.pack_loader import PackValidationError, load_and_validate_pack
from transcriptx.demo.service import (
    DemoStatusKind,
    plan_install,
    plan_remove,
    status_demo_project,
)


@pytest.mark.unit
def test_plan_install_and_remove_shapes() -> None:
    install = plan_install()
    remove = plan_remove()
    assert install.operation == "install"
    assert remove.operation == "remove"
    assert install.steps
    assert remove.steps
    assert install.pack_id


@pytest.mark.unit
def test_pack_transcript_hashes_match_bytes() -> None:
    pack = load_and_validate_pack()
    for tx in pack.transcripts:
        import hashlib

        assert hashlib.sha256(tx.bytes).hexdigest() == tx.content_sha256
        payload = json.loads(tx.bytes.decode("utf-8"))
        assert isinstance(payload.get("segments"), list)
        assert payload["segments"]


@pytest.mark.unit
def test_status_missing_without_inventory(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.core.utils.paths as paths_mod
    from dataclasses import replace as dc_replace

    built = paths_mod._build_paths()
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    built = dc_replace(
        built,
        config_dir=cfg,
        state_dir=state,
        data_dir=data,
    )
    monkeypatch.setattr(paths_mod, "PATHS", built)
    monkeypatch.setattr(paths_mod, "CONFIG_DIR", cfg)
    st = status_demo_project()
    assert st.kind == DemoStatusKind.MISSING


@pytest.mark.unit
def test_pack_validation_error_is_value_error() -> None:
    assert issubclass(PackValidationError, ValueError)


@pytest.mark.unit
def test_clear_demo_ui_caches_tolerates_missing_helpers(monkeypatch) -> None:
    from transcriptx.demo import service as svc

    monkeypatch.setattr(
        svc,
        "clear_demo_ui_caches",
        svc.clear_demo_ui_caches,
    )
    # Should not raise even outside Streamlit.
    svc.clear_demo_ui_caches()
