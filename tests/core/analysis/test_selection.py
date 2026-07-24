"""
Unit tests for analysis selection module (apply_analysis_mode_settings, filter_modules_by_mode, etc.).
"""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.selection import (
    VALID_MODES,
    VALID_PROFILES,
    analysis_preset_badge_label,
    apply_analysis_mode_settings,
    filter_modules_by_mode,
    filter_modules_for_speaker_count,
    get_recommended_modules,
)


class TestSelectionConstants:
    """Tests for selection constants."""

    def test_valid_modes(self) -> None:
        """VALID_MODES contains quick and full."""
        assert "quick" in VALID_MODES
        assert "full" in VALID_MODES

    def test_valid_profiles(self) -> None:
        """VALID_PROFILES contains expected profiles."""
        assert "balanced" in VALID_PROFILES
        assert "academic" in VALID_PROFILES
        assert "business" in VALID_PROFILES

    def test_analysis_preset_badge_label_named_only(self) -> None:
        assert analysis_preset_badge_label("quick") == "Quick"
        assert analysis_preset_badge_label("Balanced") == "Balanced"
        assert analysis_preset_badge_label("thorough") == "Thorough"
        assert analysis_preset_badge_label("custom") is None
        assert analysis_preset_badge_label(None) is None
        assert analysis_preset_badge_label("  ") is None


class TestApplyAnalysisModeSettings:
    """Tests for apply_analysis_mode_settings."""

    def test_invalid_mode_falls_back_to_quick(self) -> None:
        """Invalid mode falls back to quick."""
        with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
            mock_config = mock_get.return_value
            mock_config.analysis.quick_analysis_settings = {
                "semantic_method": "tfidf",
                "max_segments_for_semantic": 100,
                "max_semantic_comparisons": 50,
                "ner_use_light_model": True,
                "ner_max_segments": 500,
                "semantic_profile": "balanced",
            }

            apply_analysis_mode_settings("invalid_mode")

            assert mock_config.analysis.analysis_mode == "quick"

    def test_quick_mode(self) -> None:
        """Quick mode applies quick_analysis_settings."""
        with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
            mock_config = mock_get.return_value
            mock_config.analysis.quick_analysis_settings = {
                "semantic_method": "tfidf",
                "max_segments_for_semantic": 100,
                "max_semantic_comparisons": 50,
                "ner_use_light_model": True,
                "ner_max_segments": 500,
                "semantic_profile": "balanced",
            }

            apply_analysis_mode_settings("quick")

            assert mock_config.analysis.analysis_mode == "quick"
            assert mock_config.analysis.semantic_similarity_method == "tfidf"


class TestFilterModulesByMode:
    """Tests for filter_modules_by_mode."""

    def test_returns_list(self) -> None:
        """filter_modules_by_mode returns a list."""
        result = filter_modules_by_mode(["stats", "sentiment"], "quick")
        assert isinstance(result, list)

    def test_strips_retired_semantic_ids(self) -> None:
        """Retired public semantic ids are dropped (no sibling rewrite)."""
        result = filter_modules_by_mode(
            ["stats", "semantic_similarity_advanced", "semantic_similarity_v2"],
            "quick",
        )
        assert "semantic_similarity_advanced" not in result
        assert "semantic_similarity_v2" not in result
        assert "stats" in result

    def test_invalid_mode_falls_back_to_quick(self) -> None:
        """Invalid mode falls back to quick."""
        result = filter_modules_by_mode(["stats"], "invalid")
        assert isinstance(result, list)


class TestFilterModulesForSpeakerCount:
    """Tests for filter_modules_for_speaker_count."""

    def test_returns_list(self) -> None:
        """filter_modules_for_speaker_count returns a list."""
        result = filter_modules_for_speaker_count(["stats"], 2)
        assert isinstance(result, list)


class TestGetRecommendedModules:
    """Tests for get_recommended_modules."""

    def test_returns_list(self) -> None:
        """get_recommended_modules returns a list."""
        result = get_recommended_modules()
        assert isinstance(result, list)

    def test_with_transcript_targets(self) -> None:
        """get_recommended_modules accepts transcript_targets."""
        result = get_recommended_modules(
            transcript_targets=["/path/to/transcript.json"]
        )
        assert isinstance(result, list)


class TestResolveAnalysisPreset:
    """UI analysis preset → mode/profile/modules contract."""

    def test_quick_always_balanced_profile(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        resolved = resolve_analysis_preset("quick")
        assert resolved.mode == "quick"
        assert resolved.profile == "balanced"
        assert resolved.preset == "quick"
        assert isinstance(resolved.module_ids, tuple)

    def test_balanced_and_thorough_use_full_mode(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        balanced = resolve_analysis_preset("balanced")
        thorough = resolve_analysis_preset("thorough")
        assert balanced.mode == "full"
        assert balanced.profile == "balanced"
        assert thorough.mode == "full"
        assert thorough.profile == "balanced"
        assert set(balanced.module_ids).issubset(set(thorough.module_ids))

    def test_quick_excludes_llm_and_heavy(self) -> None:
        from transcriptx.core.analysis.selection import (
            is_heavy_module,
            resolve_analysis_preset,
        )
        from transcriptx.core.pipeline.module_registry import get_module_info

        quick = resolve_analysis_preset("quick")
        for mid in quick.module_ids:
            info = get_module_info(mid)
            assert info is not None
            assert not info.requires_llm
            assert not is_heavy_module(info)

    def test_balanced_llm_and_heavy_allowlists(self) -> None:
        from transcriptx.core.analysis.selection import (
            is_heavy_module,
            resolve_analysis_preset,
        )
        from transcriptx.core.pipeline.module_registry import get_module_info

        balanced = resolve_analysis_preset("balanced")
        llm = {
            mid
            for mid in balanced.module_ids
            if get_module_info(mid) and get_module_info(mid).requires_llm
        }
        heavy = {
            mid for mid in balanced.module_ids if is_heavy_module(get_module_info(mid))
        }
        assert llm <= {"llm_summary"}
        assert heavy <= {"semantic_similarity"}
        assert "llm_summary" in balanced.module_ids
        assert "semantic_similarity" in balanced.module_ids
        assert "fine_grained_emotion" not in balanced.module_ids
        assert "contextual_emotion" not in balanced.module_ids

    def test_module_override_replaces_policy(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset
        from transcriptx.core.utils.config import get_config

        cfg = get_config()
        cfg.analysis.ui_presets.quick.module_ids = ["stats", "not_a_real_module_zzz"]
        try:
            resolved = resolve_analysis_preset("quick")
            assert resolved.module_ids == ("stats",)
        finally:
            cfg.analysis.ui_presets.quick.module_ids = None

    def test_balanced_policy_knobs_filter_without_override(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset
        from transcriptx.core.utils.config import get_config

        cfg = get_config()
        original = list(cfg.analysis.ui_presets.balanced.llm_module_ids)
        cfg.analysis.ui_presets.balanced.llm_module_ids = []
        cfg.analysis.ui_presets.balanced.allow_llm = False
        try:
            resolved = resolve_analysis_preset("balanced")
            from transcriptx.core.pipeline.module_registry import get_module_info

            assert not any(
                get_module_info(mid) and get_module_info(mid).requires_llm
                for mid in resolved.module_ids
            )
        finally:
            cfg.analysis.ui_presets.balanced.allow_llm = True
            cfg.analysis.ui_presets.balanced.llm_module_ids = original

    def test_quick_excludes_modules_needing_heavy_deps(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        quick = resolve_analysis_preset("quick")
        # voice_charts_core / prosody_dashboard depend on heavy voice_features;
        # insights depends on heavy topic_modeling.
        for mid in (
            "voice_charts_core",
            "prosody_dashboard",
            "voice_features",
            "insights",
            "topic_modeling",
        ):
            assert mid not in quick.module_ids

    def test_balanced_excludes_unallowlisted_heavy_dependents(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        balanced = resolve_analysis_preset("balanced")
        assert "topic_modeling" not in balanced.module_ids
        assert "insights" not in balanced.module_ids
        assert "bertopic" not in balanced.module_ids
        assert "semantic_similarity" in balanced.module_ids
        assert "fine_grained_emotion" not in balanced.module_ids
        assert "contextual_emotion" not in balanced.module_ids

    def test_thorough_empty_allowlists_mean_all_llm_and_heavy(self) -> None:
        from transcriptx.core.analysis.selection import (
            is_heavy_module,
            resolve_analysis_preset,
        )
        from transcriptx.core.pipeline.module_registry import get_module_info

        thorough = resolve_analysis_preset("thorough")
        assert any(
            get_module_info(mid) and get_module_info(mid).requires_llm
            for mid in thorough.module_ids
        )
        assert any(is_heavy_module(get_module_info(mid)) for mid in thorough.module_ids)
        assert "llm_summary" in thorough.module_ids
        assert "llm_action_items" in thorough.module_ids
        assert "topic_modeling" in thorough.module_ids

    def test_override_prunes_when_dep_missing(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset
        from transcriptx.core.utils.config import get_config

        cfg = get_config()
        # Pick a module that hard-depends on voice_features without including it.
        cfg.analysis.ui_presets.quick.module_ids = ["voice_charts_core", "stats"]
        try:
            resolved = resolve_analysis_preset("quick")
            assert "voice_charts_core" not in resolved.module_ids
            assert "stats" in resolved.module_ids
        finally:
            cfg.analysis.ui_presets.quick.module_ids = None

    def test_effective_heavy_count_uses_category(self) -> None:
        from transcriptx.core.analysis.selection import (
            ResolvedAnalysisPreset,
            compute_effective_modules,
            is_heavy_module,
        )
        from transcriptx.core.pipeline.module_registry import get_module_info

        # topic_modeling is category=heavy but cost_tier=normal
        info = get_module_info("topic_modeling")
        assert info is not None
        assert info.cost_tier != "heavy"
        assert is_heavy_module(info)
        plan = compute_effective_modules(
            ResolvedAnalysisPreset(
                preset="custom",
                mode="full",
                profile="balanced",
                module_ids=("stats", "topic_modeling"),
            ),
            custom_qa_execution=False,
        )
        assert plan.heavy_count == 1

    def test_thorough_excludes_legacy_by_default(self) -> None:
        from transcriptx.core.analysis.selection import (
            is_legacy_module,
            resolve_analysis_preset,
        )

        thorough = resolve_analysis_preset("thorough")
        for mid in thorough.module_ids:
            assert not is_legacy_module(mid)

    def test_custom_reconciles_against_suitable(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        resolved = resolve_analysis_preset(
            "custom",
            custom_modules=["stats", "not_a_real_module_zzz"],
        )
        assert "not_a_real_module_zzz" not in resolved.module_ids
        assert resolved.profile == "balanced"
        assert resolved.mode == "full"

    def test_effective_modules_adds_custom_qa_once(self) -> None:
        from transcriptx.core.analysis.selection import (
            compute_effective_modules,
            resolve_analysis_preset,
        )

        base = resolve_analysis_preset("custom", custom_modules=["stats", "sentiment"])
        with_qa = compute_effective_modules(base, custom_qa_execution=True)
        assert with_qa.module_ids.count("llm_custom_qa") == 1
        skipped = compute_effective_modules(base, custom_qa_execution=False)
        assert "llm_custom_qa" not in skipped.module_ids

    def test_effective_modules_strip_preset_custom_qa_on_skip(self) -> None:
        from transcriptx.core.analysis.selection import (
            ResolvedAnalysisPreset,
            compute_effective_modules,
        )

        resolved = ResolvedAnalysisPreset(
            preset="custom",
            mode="full",
            profile="balanced",
            module_ids=("stats", "llm_custom_qa"),
        )
        plan = compute_effective_modules(resolved, custom_qa_execution=False)
        assert plan.module_ids == ("stats",)

    def test_is_heavy_module_cost_tier_and_category(self) -> None:
        from types import SimpleNamespace

        from transcriptx.core.analysis.selection import is_heavy_module

        assert is_heavy_module(None) is False
        assert (
            is_heavy_module(SimpleNamespace(cost_tier="normal", category="light"))
            is False
        )
        assert (
            is_heavy_module(SimpleNamespace(cost_tier="heavy", category="light"))
            is True
        )
        assert (
            is_heavy_module(SimpleNamespace(cost_tier="normal", category="heavy"))
            is True
        )

    def test_custom_empty_seeds_from_balanced(self) -> None:
        from transcriptx.core.analysis.selection import resolve_analysis_preset

        custom = resolve_analysis_preset("custom", custom_modules=[])
        balanced = resolve_analysis_preset("balanced")
        assert custom.module_ids == balanced.module_ids
        assert custom.preset == "custom"

    def test_quick_excludes_llm_custom_qa(self) -> None:
        from transcriptx.core.analysis.selection import (
            compute_effective_modules,
            resolve_analysis_preset,
        )

        quick = resolve_analysis_preset("quick")
        assert "llm_custom_qa" not in quick.module_ids
        # Even with execution flag, Quick policy should not already include it;
        # compute_effective_modules may append for Custom/Balanced flows only
        # when the caller opts in — Quick base stays free of LLM modules.
        plan = compute_effective_modules(quick, custom_qa_execution=True)
        # Flag injects the module once for run planning regardless of preset.
        assert plan.module_ids.count("llm_custom_qa") == 1


class TestSelectionHelpersAndFullMode:
    def test_analysis_preset_badge_label(self) -> None:
        from transcriptx.core.analysis.selection import analysis_preset_badge_label

        assert analysis_preset_badge_label(None) is None
        assert analysis_preset_badge_label("") is None
        assert analysis_preset_badge_label("custom") is None
        assert analysis_preset_badge_label("QUICK") == "Quick"
        assert analysis_preset_badge_label("balanced") == "Balanced"
        assert analysis_preset_badge_label("thorough") == "Thorough"

    def test_is_legacy_module(self) -> None:
        from transcriptx.core.analysis.selection import is_legacy_module

        assert is_legacy_module("not_a_module_zzz") is False

    def test_apply_full_mode_and_invalid_profile(self) -> None:
        from unittest.mock import patch

        from transcriptx.core.analysis.selection import apply_analysis_mode_settings

        with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
            cfg = mock_get.return_value
            cfg.analysis.full_analysis_settings = {
                "semantic_method": "advanced",
                "max_segments_for_semantic": 1000,
                "max_semantic_comparisons": 500,
                "ner_use_light_model": False,
                "ner_max_segments": 5000,
                "skip_geocoding": False,
                "max_segments_per_speaker": 50,
                "max_segments_for_cross_speaker": 100,
            }
            cfg.analysis.semantic_similarity = type("V2", (), {"mode": "basic"})()
            apply_analysis_mode_settings("full", profile="not-a-profile")
            assert cfg.analysis.analysis_mode == "full"
            assert cfg.analysis.quality_filtering_profile == "balanced"
            assert cfg.analysis.semantic_similarity.mode == "advanced"
            assert cfg.analysis.max_segments_per_speaker == 50
