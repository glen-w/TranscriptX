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

    resolved = resolve_analysis_preset("custom", custom_modules=["stats", "sentiment"])
    plan = compute_effective_modules(resolved, custom_qa_execution=True)
    assert len(plan.module_ids) == plan.module_ids.count(
        "stats"
    ) + plan.module_ids.count("sentiment") + plan.module_ids.count("llm_custom_qa")
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
    assert '"form_cleared": False' in source or "'form_cleared': False" in source
    assert "_execute_pending_launch" in source
    # Button path stores request then reruns; execute uses stored request.
    assert (
        'pending["request"]' in source
        or 'pending.get("request")' in source
        or 'pending["request"]' in source
    )
    assert "st.rerun()" in source
    # Flush rerun drops prior form widgets before the blocking execute.
    assert 'pending.get("form_cleared")' in source
    # Live panel (not spinner) is the in-run progress affordance.
    assert "render_slot=progress_slot" in source
    assert 'with st.spinner("Running analysis…")' not in source


@pytest.mark.unit
def test_custom_qa_picker_empty_selection_is_implicit_skip(monkeypatch) -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    DummyHomeStreamlit.session_state = {
        "run_analysis_qa_adhoc_rows": [],
    }

    class _St(DummyHomeStreamlit):
        @staticmethod
        def empty():
            return SimpleNamespace(markdown=lambda *_a, **_k: None)

        @staticmethod
        def expander(*_a, **_k):
            return DummyExpander()

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
def test_custom_qa_picker_hides_skip_and_empty_artifact_controls() -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Skip custom questions" not in source
    assert "Create an empty custom-questions result" not in source
    assert "_empty_artifact" not in source
    assert "empty_artifact" not in source


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
def test_shell_defines_review_module_remove_hover_css() -> None:
    import transcriptx.web.shell as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_review_rm_" in source
    assert "opacity: 0" in source


@pytest.mark.unit
def test_review_module_removal_queues_custom_remainder() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        apply_pending_review_module_removal,
        apply_review_module_removal,
    )

    ss: dict = {"run_analysis_preset": "Balanced"}
    ok = apply_review_module_removal(
        ss,
        key_prefix="run_analysis",
        qa_key_prefix="run_analysis_qa",
        module_ids=["stats", "sentiment", "ner"],
        remove_id="sentiment",
    )
    assert ok is True
    assert ss["run_analysis_review_modules_keep_open"] is True
    assert "run_analysis_pending_review_removal" in ss
    # Widgets must not be mutated until apply_pending (next run, before widgets).
    assert ss["run_analysis_preset"] == "Balanced"

    apply_pending_review_module_removal(ss, key_prefix="run_analysis")
    assert ss["run_analysis_preset"] == "Custom"
    assert ss["run_analysis_custom_modules"] == ["stats", "ner"]
    assert "run_analysis_custom_modules_widget" not in ss
    assert "run_analysis_pending_review_removal" not in ss


@pytest.mark.unit
def test_review_module_removal_clears_custom_qa_picker() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        apply_pending_review_module_removal,
        apply_review_module_removal,
    )

    ss: dict = {
        "run_analysis_qa_adhoc_rows": [{"id": "1", "text": "Why?"}],
        "run_analysis_qa_saved": ["Why? [G]"],
    }
    ok = apply_review_module_removal(
        ss,
        key_prefix="run_analysis",
        qa_key_prefix="run_analysis_qa",
        module_ids=["stats", "llm_custom_qa"],
        remove_id="llm_custom_qa",
    )
    assert ok is True
    apply_pending_review_module_removal(ss, key_prefix="run_analysis")
    assert ss["run_analysis_custom_modules"] == ["stats"]
    assert ss["run_analysis_qa_adhoc_rows"] == []
    assert ss["run_analysis_qa_saved"] == []


@pytest.mark.unit
def test_review_module_removal_refuses_empty_plan() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        apply_review_module_removal,
    )

    ss: dict = {}
    assert (
        apply_review_module_removal(
            ss,
            key_prefix="run_analysis",
            qa_key_prefix=None,
            module_ids=["stats"],
            remove_id="stats",
        )
        is False
    )
    assert "run_analysis_pending_review_removal" not in ss


@pytest.mark.unit
def test_compact_llm_hidden_when_no_llm_modules(monkeypatch) -> None:
    import transcriptx.web.components.llm_model_selector as mod

    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()

    monkeypatch.setattr(mod, "st", fake_st)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        lambda _mid: SimpleNamespace(requires_llm=False),
    )
    monkeypatch.setattr(mod, "_include_group_consumer", lambda _include: False)

    selection, gates, label = mod.render_compact_llm_setup(
        key_prefix="run_analysis_llm",
        selected_modules=["stats", "wordclouds"],
        include_group=False,
    )
    assert selection is None
    assert gates == []
    assert label == "no LLM modules"
    fake_st.markdown.assert_not_called()


@pytest.mark.unit
def test_compact_llm_shown_for_group_synthesis_without_module_llm(monkeypatch) -> None:
    import transcriptx.web.components.llm_model_selector as mod

    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()
    fake_st.expander = MagicMock()
    fake_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    fake_st.expander.return_value.__exit__ = MagicMock(return_value=False)

    cfg = SimpleNamespace(
        llm=SimpleNamespace(
            enabled=True,
            provider="ollama",
            model="gemma3:12b",
            base_url="http://localhost:11434",
            model_selection=None,
        ),
        analysis=SimpleNamespace(group_llm_synthesis=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(mod, "st", fake_st)
    monkeypatch.setattr(mod, "get_config", lambda: cfg)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        lambda _mid: SimpleNamespace(requires_llm=False),
    )
    monkeypatch.setattr(mod, "_include_group_consumer", lambda include: bool(include))
    monkeypatch.setattr(
        mod, "cached_list_ollama_models", lambda _url: (("gemma3:12b",), None)
    )
    monkeypatch.setattr(
        mod,
        "ProfileController",
        lambda: SimpleNamespace(
            get_active_profile=lambda _t: "default",
            list_profiles=lambda _t: ["default"],
        ),
    )
    monkeypatch.setattr(
        mod, "_load_profile_selection", lambda _label: (None, None)
    )
    monkeypatch.setattr(mod, "_apply_selection_to_session", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "_render_assignment_widgets", lambda **_k: None)
    monkeypatch.setattr(
        mod,
        "build_selection_from_session",
        lambda *_a, **_k: __import__(
            "transcriptx.core.analysis.llm_support.model_selection",
            fromlist=["LlmModelSelection"],
        ).LlmModelSelection(mode="shared", shared_model="gemma3:12b"),
    )

    selection, gates, label = mod.render_compact_llm_setup(
        key_prefix="run_analysis_llm",
        selected_modules=["stats"],
        include_group=True,
    )
    assert selection is not None
    assert gates == []
    assert isinstance(label, str)
    fake_st.markdown.assert_called()
    assert any("LLM setup" in str(call) for call in fake_st.markdown.call_args_list)


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
        analysis=SimpleNamespace(group_llm_synthesis=SimpleNamespace(enabled=False)),
    )
    monkeypatch.setattr(mod, "st", fake_st)
    monkeypatch.setattr(mod, "get_config", lambda: cfg)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        lambda _mid: SimpleNamespace(requires_llm=True),
    )
    monkeypatch.setattr(mod, "_consumer_needs_live_llm", lambda _mid: True)

    selection, gates, label = mod.render_compact_llm_setup(
        key_prefix="run_analysis_llm",
        selected_modules=["llm_summary"],
        include_group=False,
    )
    assert selection is None
    assert gates
    assert isinstance(label, str)
    fake_st.markdown.assert_called()
    assert any(
        "LLM setup" in str(call)
        for call in fake_st.markdown.call_args_list
    )


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
