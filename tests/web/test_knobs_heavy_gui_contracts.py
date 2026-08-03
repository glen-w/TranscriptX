"""Knobs-heavy GUI contracts: Settings Analysis, Custom QA, Run/Batch, Speakers voice."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.web.streamlit_doubles import DummyColumn, DummyExpander, DummyHomeStreamlit


class _Tab:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


# ── Settings → Analysis presets panel ─────────────────────────────────────────


@pytest.mark.unit
def test_analysis_presets_panel_catalogue_filters_legacy() -> None:
    from transcriptx.web.ui.settings.analysis_presets_panel import (
        _catalogue_module_ids,
        _heavy_module_ids,
        _llm_module_ids,
    )

    catalogue = _catalogue_module_ids()
    assert "stats" in catalogue
    assert "semantic_similarity" in catalogue  # current (v2 impl)
    assert "semantic_similarity_advanced" not in catalogue
    llm = _llm_module_ids(catalogue)
    heavy = _heavy_module_ids(catalogue)
    assert "llm_summary" in llm or "llm_custom_qa" in llm
    assert heavy
    assert set(llm).issubset(set(catalogue))
    assert set(heavy).issubset(set(catalogue))


@pytest.mark.unit
def test_analysis_presets_panel_seed_matches_config_and_defaults() -> None:
    from transcriptx.core.utils.config.analysis import default_ui_presets_dict
    from transcriptx.web.ui.settings.analysis_presets_panel import (
        _seed_draft_from_config,
        _seed_draft_from_defaults,
    )

    seeded = _seed_draft_from_config()
    assert set(seeded) == {"quick", "balanced", "thorough"}
    assert seeded["quick"]["allow_llm"] is False
    assert seeded["balanced"]["llm_module_ids"] == ["llm_summary"]
    assert seeded["thorough"]["include_excluded_from_default"] is True
    assert _seed_draft_from_defaults() == default_ui_presets_dict()


@pytest.mark.unit
def test_analysis_presets_panel_save_persists_ui_presets(monkeypatch) -> None:
    import transcriptx.web.ui.settings.analysis_presets_panel as mod

    patches: list[dict] = []
    DummyHomeStreamlit.session_state = {
        "settings_ui_presets_draft": mod._seed_draft_from_defaults(),
        "settings_ui_presets_gen": 0,
    }

    class _St(DummyHomeStreamlit):
        @staticmethod
        def tabs(_labels):
            return (_Tab(), _Tab(), _Tab())

        @staticmethod
        def checkbox(label, value=False, key=None, **_k):
            # Keep draft values; override checkbox stays off.
            if key and key.endswith("_use_override"):
                return False
            return value

        @staticmethod
        def multiselect(*_a, **_k):
            return []

        @staticmethod
        def button(label, key=None, **_k):
            return key == "settings_ui_presets_save"

        @staticmethod
        def success(*_a, **_k):
            return None

        @staticmethod
        def columns(_n):
            return (DummyColumn(), DummyColumn())

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "patch_project_config_keys",
        lambda updates: patches.append(updates) or updates.get("analysis", {}),
    )
    # Avoid mutating live AnalysisConfig; still exercise validate + patch call.
    monkeypatch.setattr(
        mod,
        "get_config",
        lambda: SimpleNamespace(
            analysis=SimpleNamespace(
                ui_presets=SimpleNamespace(
                    quick=SimpleNamespace(
                        allow_llm=False,
                        llm_module_ids=[],
                        allow_heavy=False,
                        heavy_module_ids=[],
                        include_excluded_from_default=False,
                        module_ids=None,
                    ),
                    balanced=SimpleNamespace(
                        allow_llm=True,
                        llm_module_ids=["llm_summary"],
                        allow_heavy=True,
                        heavy_module_ids=["semantic_similarity"],
                        include_excluded_from_default=False,
                        module_ids=None,
                    ),
                    thorough=SimpleNamespace(
                        allow_llm=True,
                        llm_module_ids=[],
                        allow_heavy=True,
                        heavy_module_ids=[],
                        include_excluded_from_default=True,
                        module_ids=None,
                    ),
                )
            )
        ),
    )
    monkeypatch.setattr(mod, "_seed_draft_from_config", mod._seed_draft_from_defaults)

    mod.render_analysis_presets_panel()

    # Save path always patches before rerun.
    assert patches
    assert "ui_presets" in patches[0]["analysis"]
    assert patches[0]["analysis"]["ui_presets"]["quick"]["allow_llm"] is False


@pytest.mark.unit
def test_analysis_presets_panel_reset_reseeds_draft(monkeypatch) -> None:
    import transcriptx.web.ui.settings.analysis_presets_panel as mod

    draft = mod._seed_draft_from_defaults()
    draft["quick"]["allow_llm"] = True
    DummyHomeStreamlit.session_state = {
        "settings_ui_presets_draft": draft,
        "settings_ui_presets_gen": 2,
    }
    reruns = {"n": 0}

    class _St(DummyHomeStreamlit):
        @staticmethod
        def tabs(_labels):
            return (_Tab(), _Tab(), _Tab())

        @staticmethod
        def checkbox(label, value=False, key=None, **_k):
            if key and key.endswith("_use_override"):
                return False
            return value

        @staticmethod
        def multiselect(*_a, **_k):
            return []

        @staticmethod
        def button(label, key=None, **_k):
            return key == "settings_ui_presets_reset"

        @staticmethod
        def columns(_n):
            return (DummyColumn(), DummyColumn())

        @staticmethod
        def rerun():
            reruns["n"] += 1

    monkeypatch.setattr(mod, "st", _St)
    mod.render_analysis_presets_panel()
    assert (
        DummyHomeStreamlit.session_state["settings_ui_presets_draft"]["quick"][
            "allow_llm"
        ]
        is False
    )
    assert DummyHomeStreamlit.session_state["settings_ui_presets_gen"] == 3
    assert reruns["n"] == 1


@pytest.mark.unit
def test_analysis_presets_panel_exposes_policy_knob_widgets() -> None:
    src = Path("src/transcriptx/web/ui/settings/analysis_presets_panel.py").read_text(
        encoding="utf-8"
    )
    for needle in (
        "Allow LLM modules",
        "Allow heavy modules",
        "Include exclude-from-default modules",
        "Override with explicit module list",
        "Save presets",
        "Reset to defaults",
        'key=f"{prefix}_allow_llm"',
        'key=f"{prefix}_allow_heavy"',
        'key=f"{prefix}_use_override"',
    ):
        assert needle in src


# ── Custom questions picker knobs ─────────────────────────────────────────────


@pytest.mark.unit
def test_custom_qa_scope_helpers_round_trip() -> None:
    from transcriptx.web.components.llm_custom_qa_picker import (
        _scope_from_label,
        _scope_label,
        _summary_scopes,
    )

    assert _scope_label(True, False) == "Global"
    assert _scope_label(False, True) == "Per speaker"
    assert _scope_label(True, True) == "Global + per speaker"
    assert _scope_from_label("Global") == (True, False)
    assert _scope_from_label("Per speaker") == (False, True)
    assert _scope_from_label("Global + per speaker") == (True, True)
    assert _summary_scopes([]) == "None"
    assert (
        _summary_scopes(
            [
                {"scopes": {"global": True, "per_speaker": False}},
                {"scopes": {"global": False, "per_speaker": True}},
            ]
        )
        == "Global and per speaker"
    )


@pytest.mark.unit
def test_custom_qa_collect_combined_skips_blank_and_scopeless() -> None:
    from transcriptx.web.components.llm_custom_qa_picker import _collect_combined

    library = {
        "Who? [G]": {
            "text": "Who?",
            "scopes": {"global": True, "per_speaker": False},
        }
    }
    combined = _collect_combined(
        ["Who? [G]"],
        library,
        [
            {"text": "  ", "global": True, "per_speaker": False},
            {"text": "Why?", "global": False, "per_speaker": False},
            {"text": "How?", "global": False, "per_speaker": True},
        ],
    )
    assert combined == [
        {"text": "Who?", "scopes": {"global": True, "per_speaker": False}},
        {"text": "How?", "scopes": {"global": False, "per_speaker": True}},
    ]


@pytest.mark.unit
def test_custom_qa_picker_adhoc_question_enables_execution(monkeypatch) -> None:
    import transcriptx.web.components.llm_custom_qa_picker as mod

    DummyHomeStreamlit.session_state = {
        "run_analysis_qa_adhoc_rows": [
            {
                "id": "row-1",
                "text": "What next?",
                "global": True,
                "per_speaker": False,
            }
        ],
        "run_analysis_qa_saved": [],
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
        def text_input(*_a, **_k):
            return "What next?"

        @staticmethod
        def selectbox(*_a, **_k):
            return "Global"

        @staticmethod
        def columns(_n):
            count = _n if isinstance(_n, int) else len(_n)
            return tuple(DummyColumn() for _ in range(count))

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
                    max_run_total_question_chars=4000,
                    max_answer_chars=800,
                )
            )
        ),
    )
    monkeypatch.setattr(mod, "structured_library_from_settings", lambda _cfg: [])

    questions, effective, execution = mod.render_custom_qa_picker(
        key_prefix="run_analysis_qa",
        always_show=True,
    )
    assert execution is True
    assert effective is not None
    assert effective.empty is False
    assert questions and questions[0]["text"] == "What next?"


# ── Shared Run Analysis / Batch Ops preset + QA wiring ────────────────────────


@pytest.mark.unit
def test_run_and_batch_share_preset_and_custom_qa_controls() -> None:
    run_src = Path("src/transcriptx/web/page_modules/run_analysis.py").read_text()
    batch_src = Path("src/transcriptx/web/page_modules/batch_ops.py").read_text()
    for src in (run_src, batch_src):
        assert "render_analysis_preset_selector" in src
        assert "render_custom_qa_picker" in src
        assert "apply_custom_qa_to_plan" in src
        assert "llm_custom_qa_questions=" in src
        assert "analysis_preset=" in src


@pytest.mark.unit
def test_apply_custom_qa_to_plan_folds_execution_flag() -> None:
    from transcriptx.core.analysis.selection import resolve_analysis_preset
    from transcriptx.web.components.analysis_preset_controls import (
        apply_custom_qa_to_plan,
    )

    resolved = resolve_analysis_preset("custom", custom_modules=["stats"])
    on = apply_custom_qa_to_plan(resolved, custom_qa_execution=True)
    off = apply_custom_qa_to_plan(resolved, custom_qa_execution=False)
    assert "llm_custom_qa" in on.module_ids
    assert "llm_custom_qa" not in off.module_ids
    assert on.custom_qa_execution is True
    assert off.custom_qa_execution is False


@pytest.mark.unit
def test_removing_custom_qa_clears_picker_session_keys() -> None:
    from transcriptx.web.components.analysis_preset_controls import (
        apply_pending_review_module_removal,
        apply_review_module_removal,
    )

    ss: dict = {
        "run_analysis_qa_adhoc_rows": [{"id": "x", "text": "Q?"}],
        "run_analysis_qa_saved": ["label"],
    }
    assert apply_review_module_removal(
        ss,
        key_prefix="run_analysis",
        qa_key_prefix="run_analysis_qa",
        module_ids=["stats", "llm_custom_qa"],
        remove_id="llm_custom_qa",
    )
    apply_pending_review_module_removal(ss, key_prefix="run_analysis")
    assert ss["run_analysis_preset"] == "Custom"
    assert ss["run_analysis_custom_modules"] == ["stats"]
    assert ss["run_analysis_qa_adhoc_rows"] == []
    assert ss["run_analysis_qa_saved"] == []


# ── Speakers / Speaker ID / Storage voice knobs ───────────────────────────────


@pytest.mark.unit
def test_speaker_id_page_wires_voice_match_knobs() -> None:
    src = Path("src/transcriptx/web/page_modules/speaker_id.py").read_text()
    for needle in (
        "ActivationBarrier",
        "voice_session_key",
        "_cb_voice_analyse_one",
        "_cb_voice_analyse_all",
        "_cb_voice_confirm",
        "_cb_voice_reject",
        "_cb_voice_leave",
        "voice_analyse_",
        "voice_analyse_all",
        "voice_confirm_",
        "voice_reject_",
        "voice_leave_",
        "query_cache_key",
        "facade.accept(",
        "facade.reject(",
        "SpeakerIdVoiceFacade",
        "Load voice suggestions",
    ):
        assert needle in src, needle


@pytest.mark.unit
def test_speakers_page_wires_voice_and_locations_knobs() -> None:
    src = Path("src/transcriptx/web/page_modules/speakers.py").read_text()
    for needle in (
        "_render_voice_controls",
        "spk_voice_bootstrap_",
        "spk_voice_promote_",
        "spk_voice_wipe_",
        "bootstrap_enrol_profile",
        "survives Docker rebuild",
        "_render_locations_map",
        "build_profile_locations_pack",
        "INCLUDE_IGNORED_SESSION_KEY",
    ):
        assert needle in src, needle


@pytest.mark.unit
def test_speakers_panel_wires_voice_privacy_knobs() -> None:
    src = Path("src/transcriptx/web/ui/settings/speakers_panel.py").read_text()
    for needle in (
        "Local voice matching",
        "voice_privacy_enable",
        "voice_privacy_revoke",
        "voice_privacy_revoke_confirm",
        "voice_wipe_resume",
        "./data",
        "bind mount",
        "permanently deletes all enrolled",
        "VoicePrivacyService",
        "privacy.voice_settings.json",
        "FEATURE_GATE_COMPLETE",
        "voice_bootstrap_max_links",
        "Save enrol link cap",
        "operator.voice_settings.json",
        "VoiceOperatorService",
    ):
        assert needle in src, needle


@pytest.mark.unit
def test_settings_questions_panel_is_custom_qa_library_surface() -> None:
    """Settings → Questions is the durable custom-QA library editor."""
    settings = Path("src/transcriptx/web/page_modules/settings.py").read_text()
    assert "Questions" in settings
    assert "render_questions_panel" in settings
    # Panel module must persist saved_questions under llm_custom_qa.
    questions_panel = Path("src/transcriptx/web/ui/settings/questions_panel.py")
    if questions_panel.is_file():
        src = questions_panel.read_text(encoding="utf-8")
        assert "patch_project_config_keys" in src
        assert "llm_custom_qa" in src or "saved_questions" in src
        assert "HOST_CONFIG_DIR" in src or "CONFIG_DIR" in src
