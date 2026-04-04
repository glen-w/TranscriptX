"""
Unit tests for output_structure.py builder/config/data classes.

These tests are fast and deterministic and target currently low-covered helper
paths used for output structure construction.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.core.utils import output_structure as output_structure_module
from transcriptx.core.utils.output_structure import (
    OutputStructure,
    OutputStructureBuilder,
    OutputStructureConfig,
    create_output_structure,
    get_output_structure_builder,
)


class TestOutputStructureConfig:
    def test_validate_accepts_default_patterns_when_parent_exists(self, tmp_path):
        config = OutputStructureConfig(base_output_dir=str(tmp_path / "outputs"))
        is_valid, errors = config.validate()
        assert is_valid
        assert errors == []

    def test_validate_rejects_missing_placeholders(self, tmp_path):
        config = OutputStructureConfig(
            base_output_dir=str(tmp_path / "outputs"),
            transcript_dir_pattern="plain-name",
            module_dir_pattern="{transcript_dir}/fixed",
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any(
            "transcript_dir_pattern must contain {base_name}" in e for e in errors
        )
        assert any("module_dir_pattern must contain {module_name}" in e for e in errors)


class TestOutputStructure:
    def test_validate_rejects_dirs_outside_module_dir(self):
        structure = OutputStructure(
            transcript_dir="/tmp/t",
            module_dir="/tmp/t/stats",
            data_dir="/tmp/other/data",
        )
        is_valid, errors = structure.validate()
        assert not is_valid
        assert any("data_dir must be within module_dir" in e for e in errors)

    def test_create_directories_creates_core_and_extra_dirs(self, tmp_path):
        structure = OutputStructure(
            transcript_dir=str(tmp_path / "transcript"),
            module_dir=str(tmp_path / "transcript" / "stats"),
            data_dir=str(tmp_path / "transcript" / "stats" / "data"),
            charts_dir=str(tmp_path / "transcript" / "stats" / "charts"),
            extra_dirs={"exports": str(tmp_path / "transcript" / "stats" / "exports")},
        )
        structure.create_directories()
        assert Path(structure.transcript_dir).exists()
        assert Path(structure.module_dir).exists()
        assert Path(structure.data_dir).exists()
        assert Path(structure.charts_dir).exists()
        assert Path(structure.extra_dirs["exports"]).exists()

    def test_to_dict_includes_only_populated_fields_and_extra_dirs(self):
        structure = OutputStructure(
            transcript_dir="/tmp/t",
            module_dir="/tmp/t/stats",
            data_dir="/tmp/t/stats/data",
            extra_dirs={"exports": "/tmp/t/stats/exports"},
        )
        as_dict = structure.to_dict()
        assert as_dict["transcript_dir"] == "/tmp/t"
        assert as_dict["module_dir"] == "/tmp/t/stats"
        assert as_dict["data_dir"] == "/tmp/t/stats/data"
        assert "charts_dir" not in as_dict
        assert as_dict["exports"] == "/tmp/t/stats/exports"


class TestOutputStructureBuilder:
    def test_create_structure_respects_toggle_flags(self, tmp_path):
        config = OutputStructureConfig(
            base_output_dir=str(tmp_path / "outputs"),
            transcript_dir_pattern="{base_output_dir}/{base_name}",
            module_dir_pattern="{transcript_dir}/{module_name}",
            use_data_dir=True,
            use_charts_dir=True,
            use_global_subdirs=False,
            use_speaker_subdirs=False,
        )
        structure = OutputStructureBuilder(config=config).create_structure(
            transcript_path=str(tmp_path / "meeting.json"),
            module_name="stats",
        )
        assert structure.data_dir is not None
        assert structure.charts_dir is not None
        assert structure.global_data_dir is None
        assert structure.speaker_data_dir is None
        assert structure.global_charts_dir is None
        assert structure.speaker_charts_dir is None
        assert Path(structure.module_dir).exists()

    def test_create_structure_adds_extra_dirs(self, tmp_path):
        config = OutputStructureConfig(
            base_output_dir=str(tmp_path / "outputs"),
            transcript_dir_pattern="{base_output_dir}/{base_name}",
            module_dir_pattern="{transcript_dir}/{module_name}",
            extra_dirs=["exports", "reports"],
        )
        structure = OutputStructureBuilder(config=config).create_structure(
            transcript_path=str(tmp_path / "meeting.json"),
            module_name="stats",
            base_name="custom_name",
        )
        assert structure.transcript_dir.endswith("custom_name")
        assert "exports" in structure.extra_dirs
        assert "reports" in structure.extra_dirs
        assert Path(structure.extra_dirs["exports"]).exists()
        assert Path(structure.extra_dirs["reports"]).exists()

    def test_load_config_from_settings_uses_output_when_present(
        self, monkeypatch, tmp_path
    ):
        fake_config = SimpleNamespace(
            output=SimpleNamespace(
                base_output_dir=str(tmp_path / "configured"),
                create_subdirectories=False,
            )
        )
        monkeypatch.setattr(output_structure_module, "get_config", lambda: fake_config)
        builder = OutputStructureBuilder(config=None)
        assert builder.config.base_output_dir == str(tmp_path / "configured")
        assert builder.config.create_subdirectories is False

    def test_load_config_from_settings_falls_back_on_error(self, monkeypatch):
        monkeypatch.setattr(
            output_structure_module,
            "get_config",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        builder = OutputStructureBuilder(config=None)
        assert isinstance(builder.config, OutputStructureConfig)

    def test_singleton_builder_and_convenience_create(self, monkeypatch, tmp_path):
        output_structure_module._default_builder = None
        config = OutputStructureConfig(
            base_output_dir=str(tmp_path / "outputs"),
            transcript_dir_pattern="{base_output_dir}/{base_name}",
            module_dir_pattern="{transcript_dir}/{module_name}",
        )
        monkeypatch.setattr(
            output_structure_module,
            "_default_builder",
            OutputStructureBuilder(config=config),
        )
        first = get_output_structure_builder()
        second = get_output_structure_builder()
        assert first is second
        structure = create_output_structure(
            transcript_path=str(tmp_path / "meeting.json"),
            module_name="stats",
        )
        assert structure.module_dir.endswith("/stats")
