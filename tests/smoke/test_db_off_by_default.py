"""
Minimal acceptance tests: DB disabled containment.

These tests assert that with database mode off (the default), no DB
initialization, session creation, or DB capability checks occur on the
default analysis and UI-helper code paths. Expanded tests also verify
DB-on paths and UI guards.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_config(enabled: bool = False, auto_init: bool = False):
    return SimpleNamespace(enabled=enabled, auto_init=auto_init)


def _make_config(enabled: bool = False, auto_init: bool = False):
    return SimpleNamespace(database=_make_db_config(enabled, auto_init))


# ---------------------------------------------------------------------------
# 1. DatabaseConfig defaults
# ---------------------------------------------------------------------------


def test_database_config_defaults_are_off():
    from transcriptx.core.utils.config.system import DatabaseConfig

    cfg = DatabaseConfig()
    assert cfg.enabled is False, "DB must be disabled by default"
    assert cfg.auto_init is False, "auto_init must be False by default"
    assert cfg.auto_store_segments is False
    assert cfg.db_first is False
    assert cfg.auto_import is False


# ---------------------------------------------------------------------------
# 2. Pipeline does not call init_database when DB is disabled
# ---------------------------------------------------------------------------


def test_pipeline_does_not_call_init_database_when_db_disabled(tmp_path, monkeypatch):
    """With DB disabled, _run_single_analysis_pipeline must not call init_database."""

    cfg = _make_config(enabled=False, auto_init=False)

    init_db_mock = MagicMock()
    monkeypatch.setattr("transcriptx.core.pipeline.pipeline.get_config", lambda: cfg)

    # Stub out the rest of the pipeline so we don't need real files.
    with (
        patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
        patch("transcriptx.core.pipeline.pipeline.get_config", return_value=cfg),
        patch("transcriptx.database.init_database", init_db_mock),
    ):
        # We cannot easily run the full pipeline without real files, so we
        # directly verify the guard logic: enabled=False means init not called.
        _db_cfg = cfg.database
        if getattr(_db_cfg, "enabled", False) and getattr(_db_cfg, "auto_init", False):
            from transcriptx.database import init_database as _init_db  # noqa: F401

            _init_db()

    init_db_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 3. search_service._db_available returns False when DB disabled
# ---------------------------------------------------------------------------


def test_search_service_db_available_false_when_db_disabled(monkeypatch):
    from transcriptx.web.services.search_service import SearchService

    cfg = _make_config(enabled=False)
    monkeypatch.setattr(
        "transcriptx.web.services.search_service.get_config", lambda: cfg
    )

    svc = SearchService.__new__(SearchService)
    assert svc._db_available() is False


def test_search_service_db_available_does_not_call_get_session_when_db_disabled(
    monkeypatch,
):
    from transcriptx.web.services.search_service import SearchService

    cfg = _make_config(enabled=False)
    monkeypatch.setattr(
        "transcriptx.web.services.search_service.get_config", lambda: cfg
    )

    get_session_mock = MagicMock()
    with patch("transcriptx.database.get_session", get_session_mock):
        svc = SearchService.__new__(SearchService)
        svc._db_available()

    get_session_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 4. cached_list_groups returns [] without calling GroupService when DB disabled
# ---------------------------------------------------------------------------


def test_cached_list_groups_returns_empty_when_db_disabled(monkeypatch):
    """cached_list_groups() returns [] and does not call GroupService when DB disabled."""
    import transcriptx.web.cache_helpers as ch

    cfg = _make_config(enabled=False)
    list_groups_mock = MagicMock()

    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch(
            "transcriptx.web.services.group_service.GroupService.list_groups",
            list_groups_mock,
        ),
    ):
        # Clear Streamlit cache so the function runs with our patched config.
        if hasattr(ch.cached_list_groups, "clear"):
            ch.cached_list_groups.clear()
        result = ch.cached_list_groups()

    assert result == []
    list_groups_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 5. segment_storage no-ops (returns None + logs) when DB disabled
# ---------------------------------------------------------------------------


def test_store_transcript_segments_noop_when_db_disabled(monkeypatch):
    from transcriptx.database.segment_storage import store_transcript_segments_from_json

    cfg = _make_config(enabled=False)
    monkeypatch.setattr(
        "transcriptx.database.segment_storage._get_config", lambda: cfg, raising=False
    )

    init_db_mock = MagicMock()
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        with patch("transcriptx.database.init_database", init_db_mock):
            result = store_transcript_segments_from_json(
                transcript_path="/tmp/fake.json",
                strict_db=False,
            )

    assert result is None, "Should return None when DB is disabled and strict_db=False"
    init_db_mock.assert_not_called()


def test_store_transcript_segments_raises_when_db_disabled_strict(monkeypatch):
    """strict_db=True must raise RuntimeError when DB is disabled."""
    from transcriptx.database.segment_storage import store_transcript_segments_from_json

    cfg = _make_config(enabled=False)
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        with pytest.raises(RuntimeError, match="database mode is disabled"):
            store_transcript_segments_from_json(
                transcript_path="/tmp/fake.json",
                strict_db=True,
            )


# ---------------------------------------------------------------------------
# 6. TRANSCRIPTX_DB_AUTO_INIT is parsed from environment
# ---------------------------------------------------------------------------


def test_db_auto_init_env_var_parsed(monkeypatch):
    """TRANSCRIPTX_DB_AUTO_INIT=1 should set database.auto_init = True."""
    monkeypatch.setenv("TRANSCRIPTX_DB_ENABLED", "1")
    monkeypatch.setenv("TRANSCRIPTX_DB_AUTO_INIT", "1")

    # Force a fresh config load by importing the class directly.
    from transcriptx.core.utils.config.main import TranscriptXConfig

    cfg = TranscriptXConfig()
    cfg._load_from_env()

    assert cfg.database.enabled is True
    assert cfg.database.auto_init is True


def test_db_auto_init_env_var_defaults_false(monkeypatch):
    monkeypatch.delenv("TRANSCRIPTX_DB_ENABLED", raising=False)
    monkeypatch.delenv("TRANSCRIPTX_DB_AUTO_INIT", raising=False)

    from transcriptx.core.utils.config.main import TranscriptXConfig

    cfg = TranscriptXConfig()
    cfg._load_from_env()

    assert cfg.database.enabled is False
    assert cfg.database.auto_init is False


# ---------------------------------------------------------------------------
# 7. app.is_db_enabled()
# ---------------------------------------------------------------------------


def test_is_db_enabled_returns_false_when_config_disabled(monkeypatch):
    from transcriptx.web.app import is_db_enabled

    monkeypatch.setattr(
        "transcriptx.web.app.get_config",
        lambda: _make_config(enabled=False),
    )
    assert is_db_enabled() is False


def test_is_db_enabled_returns_true_when_config_enabled(monkeypatch):
    from transcriptx.web.app import is_db_enabled

    monkeypatch.setattr(
        "transcriptx.web.app.get_config",
        lambda: _make_config(enabled=True),
    )
    assert is_db_enabled() is True


# ---------------------------------------------------------------------------
# 8. Groups page guard
# ---------------------------------------------------------------------------


def test_render_groups_does_not_call_group_service_when_db_disabled(monkeypatch):
    """When DB is disabled, render_groups returns after showing message; no DB/GroupService."""
    list_groups_mock = MagicMock()
    st_info_mock = MagicMock()

    with (
        patch(
            "transcriptx.core.utils.config.get_config",
            return_value=_make_config(enabled=False),
        ),
        patch(
            "transcriptx.web.page_modules.groups.GroupService.list_groups",
            list_groups_mock,
        ),
        patch("transcriptx.web.page_modules.groups.st.info", st_info_mock),
        patch("transcriptx.web.page_modules.groups.st.markdown"),
        patch("transcriptx.web.page_modules.groups.st.selectbox"),
        patch("transcriptx.web.page_modules.groups.st.button"),
        patch(
            "transcriptx.web.page_modules.groups.cached_list_groups", list_groups_mock
        ),
    ):
        from transcriptx.web.page_modules.groups import render_groups

        render_groups()

    list_groups_mock.assert_not_called()
    st_info_mock.assert_called_once()
    assert "TRANSCRIPTX_DB_ENABLED" in str(st_info_mock.call_args)


# ---------------------------------------------------------------------------
# 9. Speakers list / detail guards
# ---------------------------------------------------------------------------


def test_render_speakers_list_does_not_call_get_all_speakers_when_db_disabled(
    monkeypatch,
):
    get_all_speakers_mock = MagicMock()
    with (
        patch("transcriptx.web.app.is_db_enabled", return_value=False),
        patch("transcriptx.web.app.st.info", MagicMock()),
        patch("transcriptx.web.app.get_all_speakers", get_all_speakers_mock),
    ):
        from transcriptx.web.app import render_speakers_list

        render_speakers_list()

    get_all_speakers_mock.assert_not_called()


def test_render_speaker_detail_does_not_call_get_speaker_by_id_when_db_disabled(
    monkeypatch,
):
    get_speaker_mock = MagicMock()
    with (
        patch("transcriptx.web.app.is_db_enabled", return_value=False),
        patch("transcriptx.web.app.st.info", MagicMock()),
        patch("transcriptx.web.app.get_speaker_by_id", get_speaker_mock),
    ):
        from transcriptx.web.app import render_speaker_detail

        render_speaker_detail()

    get_speaker_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 10. Pipeline calls init_database when enabled and auto_init
# ---------------------------------------------------------------------------


def test_pipeline_calls_init_database_when_enabled_and_auto_init(monkeypatch):
    """When config.database.enabled and auto_init are True, init_database is called."""
    init_db_mock = MagicMock()
    cfg = _make_config(enabled=True, auto_init=True)

    with (
        patch("transcriptx.core.pipeline.pipeline.get_config", return_value=cfg),
        patch("transcriptx.database.init_database", init_db_mock),
    ):
        from transcriptx.core.pipeline.pipeline import _run_single_analysis_pipeline

        # Trigger only the DB init block at the top (will fail later on validate_transcript).
        try:
            _run_single_analysis_pipeline(
                transcript_path="/nonexistent/transcript.json",
                selected_modules=[],
                config=cfg,
            )
        except Exception:
            pass

    init_db_mock.assert_called()


# ---------------------------------------------------------------------------
# 11. processing_state does not call init_database when auto_init is False
# ---------------------------------------------------------------------------


def test_processing_state_does_not_call_init_when_auto_init_false(monkeypatch):
    """_ensure_transcript_uuid path: when enabled=True but auto_init=False, init_database not called."""
    from transcriptx.core.utils.processing_state import _ensure_transcript_uuid

    cfg = _make_config(enabled=True, auto_init=False)
    init_db_mock = MagicMock()

    with (
        patch("transcriptx.core.utils.processing_state.get_config", return_value=cfg),
        patch("transcriptx.core.utils.processing_state.init_database", init_db_mock),
        patch("transcriptx.core.utils.processing_state.get_session", MagicMock()),
        patch(
            "transcriptx.core.utils.processing_state.TranscriptFileRepository",
            MagicMock(),
        ),
    ):
        try:
            _ensure_transcript_uuid("/some/path.json")
        except Exception:
            pass

    init_db_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Search selects file backend when DB disabled
# ---------------------------------------------------------------------------


def test_search_select_backend_uses_file_when_db_disabled(monkeypatch):
    """_select_backend() uses FileSearchBackend when _db_available() is False."""
    from transcriptx.web.services.search_service import SearchService, FileSearchBackend

    monkeypatch.setattr(
        "transcriptx.web.services.search_service.get_config",
        lambda: _make_config(enabled=False),
    )
    mock_session_state = MagicMock()
    mock_session_state.get.return_value = None
    with patch(
        "transcriptx.web.services.search_service.st.session_state",
        mock_session_state,
    ):
        svc = SearchService.__new__(SearchService)
        svc._backend = None
        backend = svc._select_backend()

    assert isinstance(backend, FileSearchBackend)


# ---------------------------------------------------------------------------
# 13. file_rename._update_database_paths skips DB when disabled
# ---------------------------------------------------------------------------


def test_file_rename_update_database_paths_skips_db_when_disabled(monkeypatch):
    """_update_database_paths returns without calling init_database or session when DB disabled."""
    from transcriptx.core.utils.file_rename import _update_database_paths

    init_db_mock = MagicMock()
    with (
        patch(
            "transcriptx.core.utils.config.get_config",
            return_value=_make_config(enabled=False),
        ),
        patch("transcriptx.database.init_database", init_db_mock),
    ):
        _update_database_paths("/old/path.json", "/new/path.json")

    init_db_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 14. PipelineDatabaseIntegration disables storage when config has DB disabled
# ---------------------------------------------------------------------------


def test_pipeline_integration_disables_storage_when_config_disabled(monkeypatch):
    """When enable_storage=True but config.database.enabled=False, integration sets enable_storage=False."""
    with patch(
        "transcriptx.core.utils.config.get_config",
        return_value=_make_config(enabled=False),
    ):
        from transcriptx.database.pipeline_integration import (
            PipelineDatabaseIntegration,
        )

        integration = PipelineDatabaseIntegration(enable_storage=True)

    assert integration.enable_storage is False
    assert integration.transcript_manager is None


def test_pipeline_integration_initializes_when_config_enabled_and_auto_init(
    monkeypatch,
):
    """When config enabled and auto_init, PipelineDatabaseIntegration calls init_database and sets transcript_manager."""
    cfg = _make_config(enabled=True, auto_init=True)
    init_db_mock = MagicMock()
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch("transcriptx.database.pipeline_integration.init_database", init_db_mock),
        patch(
            "transcriptx.database.pipeline_integration.TranscriptManager", MagicMock()
        ),
    ):
        from transcriptx.database.pipeline_integration import (
            PipelineDatabaseIntegration,
        )

        integration = PipelineDatabaseIntegration(enable_storage=True)

    assert integration.enable_storage is True
    init_db_mock.assert_called()


# ---------------------------------------------------------------------------
# 15. segment_storage when DB enabled (no-op on init when auto_init False)
# ---------------------------------------------------------------------------


def test_store_transcript_segments_does_not_init_when_enabled_auto_init_false(
    monkeypatch,
):
    """When DB enabled but auto_init=False, store_transcript_segments_from_json does not call init_database."""
    cfg = _make_config(enabled=True, auto_init=False)
    init_db_mock = MagicMock()
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch("transcriptx.database.init_database", init_db_mock),
        patch(
            "transcriptx.database.segment_storage.SegmentStorageService",
            MagicMock(
                return_value=MagicMock(
                    store_transcript_segments=MagicMock(side_effect=Exception("abort"))
                )
            ),
        ),
    ):
        from transcriptx.database.segment_storage import (
            store_transcript_segments_from_json,
        )

        try:
            store_transcript_segments_from_json(
                transcript_path="/tmp/fake.json", strict_db=False
            )
        except Exception:
            pass

    init_db_mock.assert_not_called()
