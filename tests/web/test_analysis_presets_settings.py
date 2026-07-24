"""Settings Analysis presets panel contracts."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_settings_page_includes_analysis_tab() -> None:
    src = Path("src/transcriptx/web/page_modules/settings.py").read_text()
    assert "Analysis" in src
    assert "render_analysis_presets_panel" in src


def test_analysis_presets_panel_persists_ui_presets_key() -> None:
    src = Path(
        "src/transcriptx/web/ui/settings/analysis_presets_panel.py"
    ).read_text()
    assert "patch_project_config_keys" in src
    assert "ui_presets" in src
    assert "Reset to defaults" in src


def test_run_preset_help_points_to_settings_analysis() -> None:
    src = Path(
        "src/transcriptx/web/components/analysis_preset_controls.py"
    ).read_text()
    assert "Settings → Analysis" in src


def test_validate_ui_presets_dict_round_trip() -> None:
    from transcriptx.core.utils.config.analysis import (
        default_ui_presets_dict,
        validate_ui_presets_dict,
    )

    defaults = default_ui_presets_dict()
    dumped = validate_ui_presets_dict(defaults)
    assert dumped["quick"]["allow_llm"] is False
    assert dumped["balanced"]["llm_module_ids"] == ["llm_summary"]
    assert set(dumped["balanced"]["heavy_module_ids"]) == {
        "semantic_similarity",
        "fine_grained_emotion",
    }
    assert dumped["thorough"]["include_excluded_from_default"] is True


def test_validate_ui_presets_dict_rejects_extra_and_bad_types() -> None:
    from pydantic import ValidationError

    from transcriptx.core.utils.config.analysis import validate_ui_presets_dict

    with pytest.raises(ValidationError):
        validate_ui_presets_dict({"quick": {"allow_llm": ["not", "a", "bool"]}})
    with pytest.raises(ValidationError):
        validate_ui_presets_dict({"quick": {"llm_module_ids": "stats"}})
    with pytest.raises(ValidationError):
        validate_ui_presets_dict({"quick": {"not_a_real_knob": True}})
    with pytest.raises(ValidationError):
        validate_ui_presets_dict({"mystery_preset": {}})


def test_validate_ui_presets_partial_fills_defaults() -> None:
    from transcriptx.core.utils.config.analysis import validate_ui_presets_dict

    dumped = validate_ui_presets_dict(
        {"balanced": {"allow_llm": False, "llm_module_ids": []}}
    )
    assert dumped["balanced"]["allow_llm"] is False
    assert dumped["balanced"]["llm_module_ids"] == []
    # Unspecified presets keep model defaults.
    assert dumped["quick"]["allow_llm"] is False
    assert dumped["thorough"]["include_excluded_from_default"] is True


def test_patch_ui_presets_via_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.config.persistence import patch_project_config_keys
    from transcriptx.core.utils.config.analysis import validate_ui_presets_dict

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        '{"schema_version":1,"config":{"analysis":{}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "transcriptx.core.config.persistence.get_project_config_path",
        lambda: cfg_path,
    )
    payload = validate_ui_presets_dict(
        {"quick": {"allow_llm": True, "llm_module_ids": ["llm_custom_qa"]}}
    )
    merged = patch_project_config_keys({"analysis": {"ui_presets": payload}})
    assert merged["analysis"]["ui_presets"]["quick"]["allow_llm"] is True
    assert merged["analysis"]["ui_presets"]["quick"]["llm_module_ids"] == [
        "llm_custom_qa"
    ]


def test_resolve_reads_mutated_ui_presets_policy() -> None:
    from transcriptx.core.analysis.selection import resolve_analysis_preset
    from transcriptx.core.utils.config import get_config

    cfg = get_config()
    original_heavy = list(cfg.analysis.ui_presets.balanced.heavy_module_ids)
    cfg.analysis.ui_presets.balanced.heavy_module_ids = ["semantic_similarity"]
    try:
        resolved = resolve_analysis_preset("balanced")
        assert "semantic_similarity" in resolved.module_ids
        assert "fine_grained_emotion" not in resolved.module_ids
    finally:
        cfg.analysis.ui_presets.balanced.heavy_module_ids = original_heavy
