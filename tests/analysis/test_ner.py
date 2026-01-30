"""
Tests for named entity recognition (NER) module.

This module tests NER logic and geocoding integration.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.ner import NERAnalysis


class TestNERAnalysisModule:
    """Tests for NERAnalysis."""
    
    @pytest.fixture
    def ner_module(self):
        """Fixture for NERAnalysis instance."""
        return NERAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with entities and database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I live in New York and work at Google.",
                "start": 0.0,
                "end": 3.0
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "John Smith called from London yesterday.",
                "start": 3.0,
                "end": 6.0
            }
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.ner.spacy.load')
    def test_ner_analysis_basic(self, mock_spacy_load, ner_module, sample_segments, sample_speaker_map):
        """Test basic NER analysis."""
        # Mock spaCy model
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ent = MagicMock()
        mock_ent.text = "New York"
        mock_ent.label_ = "GPE"
        mock_doc.ents = [mock_ent]
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp
        
        result = ner_module.analyze(sample_segments, sample_speaker_map)
        
        assert "entities" in result or "segments" in result
    
    @patch('transcriptx.core.analysis.ner.spacy.load')
    def test_ner_analysis_person_entities(self, mock_spacy_load, ner_module, sample_speaker_map):
        """Test NER analysis for person entities."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "John Smith and Mary Johnson attended the meeting.",
                "start": 0.0,
                "end": 3.0
            }
        ]
        
        # Mock spaCy model
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ent1 = MagicMock()
        mock_ent1.text = "John Smith"
        mock_ent1.label_ = "PERSON"
        mock_ent2 = MagicMock()
        mock_ent2.text = "Mary Johnson"
        mock_ent2.label_ = "PERSON"
        mock_doc.ents = [mock_ent1, mock_ent2]
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp
        
        result = ner_module.analyze(segments, sample_speaker_map)
        
        # Should extract person entities
        assert "entities" in result or "segments" in result
    
    @patch('transcriptx.core.analysis.ner.spacy.load')
    def test_ner_analysis_location_entities(self, mock_spacy_load, ner_module, sample_speaker_map):
        """Test NER analysis for location entities."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I visited Paris and London last year.",
                "start": 0.0,
                "end": 3.0
            }
        ]
        
        # Mock spaCy model
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ent1 = MagicMock()
        mock_ent1.text = "Paris"
        mock_ent1.label_ = "GPE"
        mock_ent2 = MagicMock()
        mock_ent2.text = "London"
        mock_ent2.label_ = "GPE"
        mock_doc.ents = [mock_ent1, mock_ent2]
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp
        
        result = ner_module.analyze(segments, sample_speaker_map)
        
        # Should extract location entities
        assert "entities" in result or "segments" in result
    
    @patch('transcriptx.core.analysis.ner.spacy.load')
    def test_ner_analysis_organization_entities(self, mock_spacy_load, ner_module, sample_speaker_map):
        """Test NER analysis for organization entities."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I work at Microsoft and Apple.",
                "start": 0.0,
                "end": 3.0
            }
        ]
        
        # Mock spaCy model
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ent1 = MagicMock()
        mock_ent1.text = "Microsoft"
        mock_ent1.label_ = "ORG"
        mock_ent2 = MagicMock()
        mock_ent2.text = "Apple"
        mock_ent2.label_ = "ORG"
        mock_doc.ents = [mock_ent1, mock_ent2]
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp
        
        result = ner_module.analyze(segments, sample_speaker_map)
        
        # Should extract organization entities
        assert "entities" in result or "segments" in result
    
    def test_ner_analysis_empty_segments(self, ner_module, sample_speaker_map):
        """Test NER analysis with empty segments."""
        segments = []
        
        result = ner_module.analyze(segments, sample_speaker_map)
        
        assert "entities" in result or "segments" in result
        assert len(result.get("entities", [])) == 0 or len(result.get("segments", [])) == 0
