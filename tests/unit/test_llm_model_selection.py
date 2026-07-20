"""Unit tests for LLM model selection resolution and listing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import AnalysisRequest, BatchAnalysisRequest
from transcriptx.app.workflows.analysis import (
    _coerce_llm_model_selection,
    validate_analysis_readiness,
)
from transcriptx.app.workflows.batch import run_batch_analysis
from transcriptx.core.analysis.llm_support.model_selection import (
    LlmModelSelection,
    bind_llm_model_selection,
    get_bound_llm_model_selection,
    require_resolved_model,
    reset_llm_model_selection,
    resolve_module_llm_model,
    selection_from_mapping,
    selection_to_profile_config,
    validate_llm_model_selection,
)
from transcriptx.core.llm.errors import LLMModelMissingError
from transcriptx.core.llm.ollama_client import (
    list_installed_ollama_models,
    parse_ollama_tags_payload,
)
from transcriptx.web.components.llm_model_selector import (
    _UNSET_MODEL,
    _apply_selection_to_session,
    _installed_choice,
    launch_gate_reasons,
    render_llm_model_selector,
)


def _llm_cfg(**kwargs):
    selection = kwargs.pop("model_selection", None)
    base = SimpleNamespace(
        model="global-model:1",
        model_selection=selection,
    )
    return base


def test_parse_ollama_tags_payload_dedupes_and_skips_bad_rows():
    names = parse_ollama_tags_payload(
        {
            "models": [
                {"name": "a:1"},
                {"name": "a:1"},
                {"name": "  "},
                {"not_name": "x"},
                {"name": "b:2"},
            ]
        }
    )
    assert names == ["a:1", "b:2"]


def test_list_installed_ollama_models_never_raises():
    with patch(
        "transcriptx.core.llm.ollama_client.urllib.request.urlopen",
        side_effect=OSError("down"),
    ):
        result = list_installed_ollama_models("http://127.0.0.1:11434")
    assert result.models == ()
    assert result.error is not None


def test_resolve_precedence_request_over_profile_over_global():
    profile_sel = selection_from_mapping(
        {"mode": "shared", "shared_model": "profile-model"}
    )
    cfg = _llm_cfg(model_selection=profile_sel)
    request = LlmModelSelection(mode="shared", shared_model="request-model")
    token = bind_llm_model_selection(request)
    try:
        resolved = resolve_module_llm_model(cfg, "llm_summary")
        assert resolved.model == "request-model"
        assert resolved.source == "request"
    finally:
        reset_llm_model_selection(token)

    resolved = resolve_module_llm_model(cfg, "llm_summary")
    assert resolved.model == "profile-model"
    assert resolved.source == "profile"

    cfg2 = _llm_cfg(model_selection=None)
    resolved = resolve_module_llm_model(cfg2, "llm_summary")
    assert resolved.model == "global-model:1"
    assert resolved.source == "global"


def test_per_module_fallback_to_shared_then_global():
    sel = LlmModelSelection(
        mode="per_module",
        shared_model="shared-fallback",
        module_models={"llm_summary": "summary-model"},
    )
    cfg = _llm_cfg()
    token = bind_llm_model_selection(sel)
    try:
        assert resolve_module_llm_model(cfg, "llm_summary").model == "summary-model"
        assert (
            resolve_module_llm_model(cfg, "llm_action_items").model
            == "shared-fallback"
        )
    finally:
        reset_llm_model_selection(token)


def test_unknown_module_keys_stripped_on_normalize():
    sel = selection_from_mapping(
        {
            "mode": "per_module",
            "module_models": {"llm_summary": "ok", "not_a_module": "x"},
        }
    )
    assert "not_a_module" not in sel.module_models
    assert sel.module_models["llm_summary"] == "ok"


def test_selection_from_mapping_rejects_invalid_mode():
    with pytest.raises(ValueError, match="Invalid llm model selection mode"):
        selection_from_mapping({"mode": "turbo", "shared_model": "m"})


def test_validate_rejects_invalid_mode_on_mapping():
    with pytest.raises(ValueError, match="Invalid llm model selection mode"):
        validate_llm_model_selection({"mode": "weird", "shared_model": "m"})


def test_validate_profile_save_requires_shared_model():
    with pytest.raises(ValueError, match="shared_model"):
        validate_llm_model_selection(
            LlmModelSelection(mode="shared", shared_model=None),
            for_profile_save=True,
        )


def test_profile_config_roundtrip():
    sel = validate_llm_model_selection(
        LlmModelSelection(
            mode="per_module",
            shared_model="shared:1",
            module_models={"llm_summary": "sum:1", "bogus": "x"},
        ),
        for_profile_save=True,
    )
    payload = selection_to_profile_config(sel)
    restored = selection_from_mapping(payload)
    assert restored.mode == "per_module"
    assert restored.shared_model == "shared:1"
    assert restored.module_models == {"llm_summary": "sum:1"}


def test_require_resolved_model_raises_when_empty_global():
    cfg = SimpleNamespace(model="", model_selection=None)
    with patch(
        "transcriptx.core.analysis.llm_support.model_selection.DEFAULT_OLLAMA_MODEL",
        "",
    ):
        with pytest.raises(LLMModelMissingError):
            require_resolved_model(cfg, "llm_summary")


def test_coerce_none_preserves_omit():
    assert _coerce_llm_model_selection(None) is None


def test_coerce_rejects_unsupported_types():
    with pytest.raises(ValueError, match="mapping or LlmModelSelection"):
        _coerce_llm_model_selection("qwen3:8b")


def test_coerce_rejects_invalid_mode_dict():
    with pytest.raises(ValueError, match="Invalid llm model selection mode"):
        _coerce_llm_model_selection({"mode": "turbo", "shared_model": "m"})


def test_analysis_readiness_rejects_invalid_selection(tmp_path: Path):
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    request = AnalysisRequest(
        transcript_path=transcript,
        llm_model_selection={"mode": "nope", "shared_model": "m"},
    )
    errors = validate_analysis_readiness(request)
    assert any("llm_model_selection" in e for e in errors)


def test_group_readiness_rejects_invalid_selection():
    from transcriptx.app.models.requests import GroupAnalysisRequest
    from transcriptx.app.workflows.analysis import validate_group_analysis_readiness

    cfg = SimpleNamespace(group_analysis=SimpleNamespace(enabled=True))
    member = SimpleNamespace(file_path="/tmp/does-not-need-to-exist-yet.json")
    with patch(
        "transcriptx.app.workflows.analysis.get_config", return_value=cfg
    ), patch(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        return_value=("group", [member]),
    ):
        # Still fails on missing files before selection check when no paths exist
        pass

    # Use a real existing path so readiness reaches llm_model_selection validation
    with patch(
        "transcriptx.app.workflows.analysis.get_config", return_value=cfg
    ), patch(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        return_value=(
            "group",
            [SimpleNamespace(file_path=str(Path(__file__).resolve()))],
        ),
    ):
        errors = validate_group_analysis_readiness(
            GroupAnalysisRequest(
                group_uuid="any",
                llm_model_selection={"mode": "turbo", "shared_model": "m"},
            )
        )
    assert any("llm_model_selection" in e for e in errors)


def test_profile_label_roundtrip():
    from transcriptx.web.components.llm_model_selector import (
        _PROJECT_DEFAULT_LABEL,
        _profile_display_label,
        _profile_storage_name,
    )

    assert _profile_storage_name(_PROJECT_DEFAULT_LABEL) == "default"
    assert _profile_display_label("default") == _PROJECT_DEFAULT_LABEL
    assert _profile_storage_name("my_pack") == "my_pack"


def test_batch_rejects_invalid_selection_before_runs():
    result = run_batch_analysis(
        BatchAnalysisRequest(
            transcript_paths=[Path("/tmp/does-not-matter.json")],
            llm_model_selection="not-a-selection",
        )
    )
    assert result.success is False
    assert any("llm_model_selection" in e for e in result.errors)


def test_launch_gate_blocks_when_llm_modules_selected_without_ollama():
    with patch(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        return_value=SimpleNamespace(requires_llm=True),
    ):
        reasons = launch_gate_reasons(
            selection=LlmModelSelection(mode="shared", shared_model="m"),
            selected_modules=["llm_summary"],
            installed=("m",),
            list_error=None,
            include_group=False,
            llm_enabled=False,
            provider="null",
        )
    assert reasons
    assert "disabled" in reasons[0].lower() or "ollama" in reasons[0].lower()


def test_launch_gate_blocks_empty_tags_and_bad_shared_pick():
    info = SimpleNamespace(requires_llm=True)
    with patch(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        return_value=info,
    ):
        empty = launch_gate_reasons(
            selection=LlmModelSelection(mode="shared", shared_model=None),
            selected_modules=["llm_summary"],
            installed=(),
            list_error="probe failed",
            include_group=False,
            llm_enabled=True,
            provider="ollama",
        )
        assert any("Cannot reach Ollama" in r for r in empty)
        assert any("No Ollama models" in r for r in empty)

        bad = launch_gate_reasons(
            selection=LlmModelSelection(mode="shared", shared_model="missing"),
            selected_modules=["llm_summary"],
            installed=("installed:1",),
            list_error=None,
            include_group=False,
            llm_enabled=True,
            provider="ollama",
        )
        assert any("shared model" in r.lower() for r in bad)


def test_launch_gate_group_synthesis_enabled_needs_llm():
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=True)
        )
    )
    with patch(
        "transcriptx.web.components.llm_model_selector.get_config",
        return_value=cfg,
    ):
        with patch(
            "transcriptx.core.pipeline.module_registry.get_module_info",
            return_value=SimpleNamespace(requires_llm=False),
        ):
            reasons = launch_gate_reasons(
                selection=LlmModelSelection(mode="shared", shared_model=None),
                selected_modules=["summary"],
                installed=("m:1",),
                list_error=None,
                include_group=True,
                llm_enabled=True,
                provider="ollama",
            )
    assert any("shared model" in r.lower() for r in reasons)


def test_launch_gate_group_synthesis_disabled_skips_consumer():
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=False)
        )
    )
    info_map = {
        "summary": SimpleNamespace(requires_llm=False),
        "llm_summary": SimpleNamespace(requires_llm=True),
    }
    with patch(
        "transcriptx.web.components.llm_model_selector.get_config",
        return_value=cfg,
    ):
        with patch(
            "transcriptx.core.pipeline.module_registry.get_module_info",
            side_effect=lambda mid: info_map.get(
                mid, SimpleNamespace(requires_llm=False)
            ),
        ):
            reasons = launch_gate_reasons(
                selection=LlmModelSelection(
                    mode="per_module",
                    shared_model=None,
                    module_models={"llm_summary": "m:1"},
                ),
                selected_modules=["llm_summary"],
                installed=("m:1",),
                list_error=None,
                include_group=True,
                llm_enabled=True,
                provider="ollama",
            )
    assert not any("group_llm_synthesis" in r for r in reasons)


def test_installed_choice_unsets_unavailable():
    assert _installed_choice("gone:1", ("kept:1",)) is None
    assert _installed_choice("kept:1", ("kept:1",)) == "kept:1"


def test_apply_selection_does_not_substitute(monkeypatch):
    session: dict[str, Any] = {}
    fake_st = SimpleNamespace(session_state=session)
    monkeypatch.setattr(
        "transcriptx.web.components.llm_model_selector.st", fake_st
    )
    notes = _apply_selection_to_session(
        "pfx",
        LlmModelSelection(mode="shared", shared_model="missing:9"),
        installed=("installed:1",),
    )
    assert session["pfx_shared_model"] == _UNSET_MODEL
    assert any("missing:9" in n for n in notes)


def test_render_early_return_gates_when_llm_disabled():
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()
    fake_st.warning = MagicMock()
    cfg = SimpleNamespace(
        llm=SimpleNamespace(enabled=False, provider="null", model=None),
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=False)
        ),
    )
    with patch(
        "transcriptx.web.components.llm_model_selector.st", fake_st
    ), patch(
        "transcriptx.web.components.llm_model_selector.get_config",
        return_value=cfg,
    ), patch(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        return_value=SimpleNamespace(requires_llm=True),
    ):
        selection, gates = render_llm_model_selector(
            key_prefix="run_analysis_llm",
            selected_modules=["llm_summary"],
            include_group=False,
        )
    assert selection is None
    assert gates
    assert any("disabled" in g.lower() or "ollama" in g.lower() for g in gates)


def test_selection_none_compat_uses_global():
    cfg = _llm_cfg()
    assert get_bound_llm_model_selection() is None
    resolved = resolve_module_llm_model(cfg, "llm_summary", selection_override=None)
    assert resolved.source == "global"
    assert resolved.model == "global-model:1"
