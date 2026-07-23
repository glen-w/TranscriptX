"""Focused GUI contracts for the decluttered Run Analysis page."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.web.streamlit_doubles import DummyExpander, DummyHomeStreamlit


@pytest.mark.unit
def test_migrate_legacy_keys_quick_to_preset() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        migrate_legacy_analysis_keys,
    )

    ss: dict = {
        "run_analysis_mode": "quick",
        "run_analysis_profile": "academic",
        "run_analysis_use_defaults": True,
    }
    migrate_legacy_analysis_keys(ss, key_prefix="run_analysis")
    assert ss["run_analysis_preset"] == "Quick"
    assert "run_analysis_mode" not in ss
    assert "run_analysis_profile" not in ss
    assert ss["run_analysis_legacy_analysis_migrated"] is True


@pytest.mark.unit
def test_migrate_legacy_keys_custom_modules_preserved() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        migrate_legacy_analysis_keys,
    )

    ss: dict = {
        "run_analysis_mode": "full",
        "run_analysis_use_defaults": False,
        "run_analysis_modules": ["stats", "sentiment"],
    }
    migrate_legacy_analysis_keys(ss, key_prefix="run_analysis")
    assert ss["run_analysis_preset"] == "Custom"
    assert ss["run_analysis_custom_modules"] == ["stats", "sentiment"]


@pytest.mark.unit
def test_migrate_legacy_keys_idempotent() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        migrate_legacy_analysis_keys,
    )

    ss: dict = {
        "run_analysis_preset": "Thorough",
        "run_analysis_mode": "quick",
        "run_analysis_legacy_analysis_migrated": True,
    }
    migrate_legacy_analysis_keys(ss, key_prefix="run_analysis")
    assert ss["run_analysis_preset"] == "Thorough"
    assert "run_analysis_mode" not in ss


@pytest.mark.unit
def test_custom_modules_survive_preset_flip_via_stored_key() -> None:
    """Custom selection is resolved from the durable list, not from Balanced."""
    from transcriptx.core.analysis.selection import resolve_analysis_preset

    stored = ("stats", "sentiment")
    balanced = resolve_analysis_preset("balanced")
    custom_again = resolve_analysis_preset("custom", custom_modules=stored)
    assert custom_again.preset == "custom"
    assert custom_again.module_ids == stored
    # Balanced may be a larger set; Custom must not silently expand to Balanced.
    assert custom_again.module_ids != balanced.module_ids or len(stored) == len(
        balanced.module_ids
    )


@pytest.mark.unit
def test_target_change_reconciles_incompatible_custom_modules() -> None:
    from transcriptx.core.analysis.selection import reconcile_custom_modules

    kept, removed = reconcile_custom_modules(
        ["stats", "ghost_module", "sentiment"],
        suitable=["stats", "sentiment", "ner"],
    )
    assert kept == ("stats", "sentiment")
    assert removed == ("ghost_module",)


@pytest.mark.unit
def test_footer_module_count_matches_effective_plan() -> None:
    from transcriptx.core.analysis.selection import (
        compute_effective_modules,
        resolve_analysis_preset,
    )

    resolved = resolve_analysis_preset(
        "custom", custom_modules=["stats", "sentiment"]
    )
    plan = compute_effective_modules(resolved, custom_qa_execution=True)
    assert len(plan.module_ids) == plan.module_ids.count("stats") + plan.module_ids.count(
        "sentiment"
    ) + plan.module_ids.count("llm_custom_qa")
    assert "llm_custom_qa" in plan.module_ids
    # Launch authority must use plan.module_ids length.
    assert len(plan.module_ids) >= 3


@pytest.mark.unit
def test_settings_page_includes_models_tab() -> None:
    import transcriptx.web.page_modules.settings as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Models" in source
    assert "render_models_panel" in source


@pytest.mark.unit
def test_models_panel_delegates_to_settings_renderer() -> None:
    import transcriptx.web.ui.settings.models_panel as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_llm_models_settings_panel" in source


@pytest.mark.unit
def test_pending_launch_snapshot_is_launch_authority() -> None:
    import transcriptx.web.page_modules.run_analysis as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_PENDING_LAUNCH_KEY" in source
    assert '"started": False' in source or "'started': False" in source
    assert "_execute_pending_launch" in source
    # Button path stores request then reruns; execute uses stored request.
    assert 'pending["request"]' in source or "pending.get(\"request\")" in source or 'pending["request"]' in source
    assert "st.rerun()" in source


@pytest.mark.unit
def test_custom_qa_picker_skip_strips_execution(monkeypatch) -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    DummyHomeStreamlit.session_state = {
        "run_analysis_qa_adhoc_rows": [],
        "run_analysis_qa_skip": True,
        "run_analysis_qa_empty_artifact": False,
    }

    class _St(DummyHomeStreamlit):
        @staticmethod
        def empty():
            return SimpleNamespace(markdown=lambda *_a, **_k: None)

        @staticmethod
        def expander(*_a, **_k):
            return DummyExpander()

        @staticmethod
        def checkbox(label, value=False, key=None, **_kwargs):
            if key is not None and key in DummyHomeStreamlit.session_state:
                return bool(DummyHomeStreamlit.session_state[key])
            return value

        @staticmethod
        def multiselect(*_a, **_k):
            return []

        @staticmethod
        def toast(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(
            analysis=SimpleNamespace(
                llm_custom_qa=SimpleNamespace(
                    max_questions_per_run=8,
                    saved_questions=[],
                    max_question_chars=500,
                    max_library_questions=50,
                    max_library_total_question_chars=5000,
                )
            )
        ),
    )
    monkeypatch.setattr(mod, "structured_library_from_settings", lambda _cfg: [])

    questions, effective, execution = mod.render_custom_qa_picker(
        key_prefix="run_analysis_qa",
        always_show=True,
    )
    assert questions is None
    assert effective is None
    assert execution is False


@pytest.mark.unit
def test_custom_qa_picker_empty_artifact_executes(monkeypatch) -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    DummyHomeStreamlit.session_state = {
        "run_analysis_qa_adhoc_rows": [],
        "run_analysis_qa_skip": False,
        "run_analysis_qa_empty_artifact": True,
    }

    class _St(DummyHomeStreamlit):
        @staticmethod
        def empty():
            return SimpleNamespace(markdown=lambda *_a, **_k: None)

        @staticmethod
        def expander(*_a, **_k):
            return DummyExpander()

        @staticmethod
        def checkbox(label, value=False, key=None, **_kwargs):
            if key is not None and key in DummyHomeStreamlit.session_state:
                return bool(DummyHomeStreamlit.session_state[key])
            return value

        @staticmethod
        def multiselect(*_a, **_k):
            return []

    monkeypatch.setattr(mod, "st", _St)
    cfg = SimpleNamespace(
        max_questions_per_run=8,
        saved_questions=[],
        max_question_chars=500,
        max_library_questions=50,
        max_library_total_question_chars=5000,
    )
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(analysis=SimpleNamespace(llm_custom_qa=cfg)),
    )
    monkeypatch.setattr(mod, "structured_library_from_settings", lambda _cfg: [])
    monkeypatch.setattr(
        mod,
        "resolve_effective_custom_qa_questions",
        lambda **_k: SimpleNamespace(structured=[]),
    )

    questions, effective, execution = mod.render_custom_qa_picker(
        key_prefix="run_analysis_qa",
        always_show=True,
    )
    assert questions == []
    assert effective is not None
    assert execution is True


@pytest.mark.unit
def test_custom_qa_row_keys_use_stable_ids_not_indexes() -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert 'f"{key_prefix}_adhoc_text_{rid}"' in source
    assert 'f"{key_prefix}_adhoc_scope_{rid}"' in source
    assert 'f"{key_prefix}_adhoc_text_{i}"' not in source
    assert '"id": str(uuid.uuid4())' in source or "uuid.uuid4()" in source


@pytest.mark.unit
def test_shell_defines_keyed_run_analysis_footer_css() -> None:
    import transcriptx.web.shell as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "tx-run-analysis-footer" in source
    assert "position: sticky" in source


@pytest.mark.unit
def test_compact_llm_degrades_without_ollama(monkeypatch) -> None:
    import transcriptx.web.components.llm_model_selector as mod

    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()
    fake_st.expander = MagicMock()
    fake_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    fake_st.expander.return_value.__exit__ = MagicMock(return_value=False)

    cfg = SimpleNamespace(
        llm=SimpleNamespace(enabled=False, provider="null", model=None, base_url=None),
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=False)
        ),
    )
    monkeypatch.setattr(mod, "st", fake_st)
    monkeypatch.setattr(mod, "get_config", lambda: cfg)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        lambda _mid: SimpleNamespace(requires_llm=False),
    )

    selection, gates, label = mod.render_compact_llm_setup(
        key_prefix="run_analysis_llm",
        selected_modules=["stats"],
        include_group=False,
    )
    assert selection is None
    assert gates == []
    assert isinstance(label, str)


@pytest.mark.unit
def test_batch_and_run_share_preset_helper_import() -> None:
    import transcriptx.web.page_modules.batch_ops as batch
    import transcriptx.web.page_modules.run_analysis as run

    batch_src = Path(batch.__file__).read_text(encoding="utf-8")
    run_src = Path(run.__file__).read_text(encoding="utf-8")
    assert "render_analysis_preset_selector" in batch_src
    assert "render_analysis_preset_selector" in run_src
    assert "render_compact_llm_setup" in batch_src
    assert "render_compact_llm_setup" in run_src
