"""
Unit tests for analysis selection module (apply_analysis_mode_settings, filter_modules_by_mode, etc.).
"""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.selection import (
    VALID_MODES,
    VALID_PROFILES,
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

    def test_quick_mode_filters_semantic_advanced(self) -> None:
        """Quick mode filters out semantic_similarity_advanced."""
        with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
            mock_config = mock_get.return_value
            mock_config.analysis.quick_analysis_settings = {
                "skip_advanced_semantic": True
            }

            result = filter_modules_by_mode(
                ["stats", "semantic_similarity_advanced"], "quick"
            )

            assert "semantic_similarity_advanced" not in result

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

        base = resolve_analysis_preset(
            "custom", custom_modules=["stats", "sentiment"]
        )
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
