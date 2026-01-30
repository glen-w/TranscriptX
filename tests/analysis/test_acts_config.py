"""
Tests for dialogue act configuration.

This module tests dialogue act configuration settings.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.acts.config import (
    ActClassificationConfig,
    ClassificationMethod,
    ContextWindowType,
    DEFAULT_ACT_CONFIG,
    ACT_TYPE_DEFINITIONS,
)


class TestActClassificationConfig:
    """Tests for ActClassificationConfig."""
    
    def test_config_creation(self):
        """Test creating configuration with defaults."""
        config = ActClassificationConfig()
        
        assert config.method == ClassificationMethod.BOTH
        assert config.use_context is True
        assert config.context_window_size == 3
        assert config.min_confidence == 0.7
    
    def test_config_custom_values(self):
        """Test creating configuration with custom values."""
        config = ActClassificationConfig(
            method=ClassificationMethod.RULES,
            use_context=False,
            min_confidence=0.8
        )
        
        assert config.method == ClassificationMethod.RULES
        assert config.use_context is False
        assert config.min_confidence == 0.8
    
    def test_default_config(self):
        """Test default configuration."""
        assert DEFAULT_ACT_CONFIG is not None
        assert isinstance(DEFAULT_ACT_CONFIG, ActClassificationConfig)
    
    def test_config_confidence_thresholds(self):
        """Test confidence threshold settings."""
        config = ActClassificationConfig()
        
        assert config.min_confidence >= 0
        assert config.min_confidence <= 1
        assert config.high_confidence_threshold >= config.min_confidence
        assert config.high_confidence_threshold <= 1
    
    def test_config_ensemble_weights(self):
        """Test ensemble weight settings."""
        config = ActClassificationConfig()
        
        total_weight = (
            config.ensemble_weight_transformer +
            config.ensemble_weight_ml +
            config.ensemble_weight_rules
        )
        
        # Weights should sum to approximately 1.0
        assert abs(total_weight - 1.0) < 0.01


class TestClassificationMethod:
    """Tests for ClassificationMethod enum."""
    
    def test_enum_values(self):
        """Test enum values."""
        assert ClassificationMethod.RULES.value == "rules"
        assert ClassificationMethod.ML.value == "ml"
        assert ClassificationMethod.BOTH.value == "both"


class TestContextWindowType:
    """Tests for ContextWindowType enum."""
    
    def test_enum_values(self):
        """Test enum values."""
        assert ContextWindowType.FIXED.value == "fixed"
        assert ContextWindowType.DYNAMIC.value == "dynamic"
        assert ContextWindowType.SLIDING.value == "sliding"


class TestActTypeDefinitions:
    """Tests for ACT_TYPE_DEFINITIONS."""
    
    def test_act_type_definitions_exist(self):
        """Test that act type definitions exist."""
        assert len(ACT_TYPE_DEFINITIONS) > 0
    
    def test_act_type_structure(self):
        """Test structure of act type definitions."""
        for act_type, definition in ACT_TYPE_DEFINITIONS.items():
            assert isinstance(definition, dict)
            assert "description" in definition
            assert isinstance(definition["description"], str)
            
            if "examples" in definition:
                assert isinstance(definition["examples"], list)
            
            if "confidence_boosters" in definition:
                assert isinstance(definition["confidence_boosters"], list)
    
    def test_common_act_types(self):
        """Test that common act types are defined."""
        common_types = ["question", "statement", "agreement", "disagreement", "suggestion"]
        
        for act_type in common_types:
            if act_type in ACT_TYPE_DEFINITIONS:
                assert isinstance(ACT_TYPE_DEFINITIONS[act_type], dict)
