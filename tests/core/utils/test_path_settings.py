"""
Tests for path settings (PathSettings, path constants, serialization).

Covers path-resolution behaviour, env overrides, bootstrap, and config
serialization after the str -> Path migration.
"""

import json
from pathlib import Path


from transcriptx.core.utils import paths as paths_module


class TestPathSettingsStructure:
    """Path contract: processing_state_file under state_dir, profiles_dir under config_dir."""

    def test_processing_state_file_under_state_dir(self):
        assert (
            paths_module.PROCESSING_STATE_FILE
            == paths_module.STATE_DIR / "processing_state.json"
        )
        assert (
            paths_module.PATHS.processing_state_file
            == paths_module.PATHS.state_dir / "processing_state.json"
        )

    def test_profiles_dir_under_config_dir(self):
        assert (
            paths_module.PATHS.profiles_dir
            == paths_module.PATHS.config_dir / "profiles"
        )
        assert paths_module.PROFILES_DIR == paths_module.CONFIG_DIR / "profiles"

    def test_all_constants_are_path_objects(self):
        for name in (
            "PROJECT_ROOT",
            "DATA_DIR",
            "CONFIG_DIR",
            "RECORDINGS_DIR",
            "DIARISED_TRANSCRIPTS_DIR",
            "READABLE_TRANSCRIPTS_DIR",
            "OUTPUTS_DIR",
            "GROUP_OUTPUTS_DIR",
            "PROFILES_DIR",
            "WAV_STORAGE_DIR",
            "PREPROCESSING_DIR",
            "PROCESSING_STATE_FILE",
            "STATE_DIR",
        ):
            val = getattr(paths_module, name)
            assert isinstance(val, Path), f"{name} should be Path, got {type(val)}"


class TestEnvOverride:
    """Env overrides are applied when _build_paths() runs (e.g. after bootstrap)."""

    def test_data_dir_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
        result = paths_module._build_paths()
        assert result.data_dir == tmp_path
        assert result.state_dir == tmp_path / "state"
        assert (
            result.processing_state_file == tmp_path / "state" / "processing_state.json"
        )

    def test_recordings_and_transcripts_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("TRANSCRIPTX_RECORDINGS_DIR", str(tmp_path / "recordings"))
        monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(tmp_path / "transcripts"))
        result = paths_module._build_paths()
        assert result.recordings_dir == tmp_path / "recordings"
        assert result.transcripts_dir == tmp_path / "transcripts"
        assert result.readable_transcripts_dir == tmp_path / "transcripts" / "readable"

    def test_mounted_library_dirs_separate_from_data(self, monkeypatch):
        """With DATA_DIR=/data and RECORDINGS_DIR=/recordings, nothing nests under /data."""
        monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", "/data")
        monkeypatch.setenv("TRANSCRIPTX_RECORDINGS_DIR", "/recordings")
        monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", "/transcripts")
        result = paths_module._build_paths()
        assert result.recordings_dir == Path("/recordings")
        assert result.transcripts_dir == Path("/transcripts")
        assert result.data_dir == Path("/data")
        # Recordings and transcripts must not be under data when overridden
        assert not str(result.recordings_dir).startswith(str(result.data_dir))
        assert not str(result.transcripts_dir).startswith(str(result.data_dir))


class TestConfigSerialization:
    """Config serialization works with Path -> str at boundary."""

    def test_workflow_config_defaults_are_str(self):
        from transcriptx.core.utils.config.workflow import (
            OutputConfig,
            InputConfig,
            GroupAnalysisConfig,
        )

        out = OutputConfig()
        assert isinstance(out.base_output_dir, str)
        assert isinstance(out.default_audio_folder, str)
        assert isinstance(out.default_transcript_folder, str)
        inp = InputConfig()
        assert isinstance(inp.recordings_folders, list)
        assert all(isinstance(p, str) for p in inp.recordings_folders)
        grp = GroupAnalysisConfig()
        assert isinstance(grp.output_dir, str)

    def test_json_dump_config_with_default_str(self):
        from transcriptx.core.utils.config.workflow import OutputConfig

        out = OutputConfig()
        config_dict = {
            "base_output_dir": out.base_output_dir,
            "default_audio_folder": out.default_audio_folder,
            "default_transcript_folder": out.default_transcript_folder,
        }
        json_str = json.dumps(config_dict, indent=2, default=str)
        loaded = json.loads(json_str)
        for key, value in loaded.items():
            assert isinstance(
                value, str
            ), f"{key} should be str in JSON, got {type(value)}"
            assert "Path" not in value and "PosixPath" not in value

    def test_resolver_env_strip_does_not_affect_path_constants(self):
        from transcriptx.core.utils.paths import RECORDINGS_DIR
        from transcriptx.core.config.resolver import resolve_effective_config

        original = RECORDINGS_DIR
        resolve_effective_config()
        assert RECORDINGS_DIR == original


class TestEnsureDataDirs:
    """ensure_data_dirs runs without error."""

    def test_ensure_data_dirs_does_not_raise(self):
        paths_module.ensure_data_dirs()
        # No exception; in tests TRANSCRIPTX_OUTPUT_DIR is often set to .test_outputs
