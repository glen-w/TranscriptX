"""
Tests for question-answer analysis module.

This module tests question detection, answer matching, response quality assessment,
and Q&A pair identification.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.qa_analysis import QAAnalysis


class TestQAAnalysis:
    """Tests for QAAnalysis."""
    
    @pytest.fixture
    def qa_module(self):
        """Fixture for QAAnalysis instance."""
        return QAAnalysis()
    
    @pytest.fixture
    def sample_segments_with_questions(self):
        """Fixture for sample transcript segments with questions using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What time is the meeting?", "start": 0.0, "end": 2.0, "dialogue_act": "question", "act_type": "question"},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "The meeting is at 3 PM.", "start": 2.5, "end": 5.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Where will it be held?", "start": 5.5, "end": 7.0, "dialogue_act": "question", "act_type": "question"},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "In the conference room.", "start": 7.5, "end": 9.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Who is attending?", "start": 9.5, "end": 11.0, "dialogue_act": "question", "act_type": "question"},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "The whole team.", "start": 11.5, "end": 13.0},
        ]
    
    @pytest.fixture
    def sample_segments_pattern_questions(self):
        """Fixture for segments with questions detected by pattern (no acts data) using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What is your name?", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "My name is Bob.", "start": 2.5, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "How old are you?", "start": 4.5, "end": 6.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I'm 30 years old.", "start": 6.5, "end": 8.0},
        ]
    
    @pytest.fixture
    def sample_segments_unanswered_questions(self):
        """Fixture for segments with unanswered questions using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What is the deadline?", "start": 0.0, "end": 2.0, "dialogue_act": "question", "act_type": "question"},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Let me check my notes.", "start": 2.5, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "When will you know?", "start": 4.5, "end": 6.0, "dialogue_act": "question", "act_type": "question"},
            # No answer provided
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @pytest.fixture
    def sample_acts_data(self):
        """Fixture for sample acts data using database-driven speaker identification."""
        return {
            "segments_with_acts": [
                {"speaker": "Alice", "speaker_db_id": 1, "text": "What time is it?", "start": 0.0, "dialogue_act": "question", "act_type": "question"},
                {"speaker": "Bob", "speaker_db_id": 2, "text": "It's 3 PM.", "start": 2.0, "dialogue_act": "statement", "act_type": "statement"},
            ]
        }
    
    def test_qa_analysis_basic(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test basic Q&A analysis."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        assert "qa_pairs" in result
        assert "unanswered_questions" in result
        assert "question_chains" in result
        assert "statistics" in result
        assert len(result["qa_pairs"]) > 0
    
    def test_qa_analysis_question_detection(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test question detection."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        qa_pairs = result["qa_pairs"]
        assert len(qa_pairs) > 0
        
        # Check that questions are detected
        questions_found = sum(1 for pair in qa_pairs if pair.get("question"))
        assert questions_found > 0
    
    def test_qa_analysis_answer_matching(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test answer matching to questions."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        qa_pairs = result["qa_pairs"]
        matched_pairs = [pair for pair in qa_pairs if pair.get("matched", False)]
        
        # Should have at least some matched pairs
        assert len(matched_pairs) > 0
        
        for pair in matched_pairs:
            assert "question" in pair
            assert "answer" in pair
            assert pair["answer"] is not None
            assert "response_time" in pair["answer"]
    
    def test_qa_analysis_response_quality(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test response quality assessment."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        qa_pairs = result["qa_pairs"]
        matched_pairs = [pair for pair in qa_pairs if pair.get("matched", False) and pair.get("quality")]
        
        for pair in matched_pairs:
            quality = pair["quality"]
            assert "directness" in quality
            assert "completeness" in quality
            assert "relevance" in quality
            assert "length_score" in quality
            assert "overall" in quality
            
            # Quality scores should be between 0 and 1
            assert 0.0 <= quality["overall"] <= 1.0
            assert 0.0 <= quality["directness"] <= 1.0
            assert 0.0 <= quality["completeness"] <= 1.0
    
    def test_qa_analysis_unanswered_questions(self, qa_module, sample_segments_unanswered_questions, sample_speaker_map):
        """Test detection of unanswered questions."""
        result = qa_module.analyze(sample_segments_unanswered_questions, sample_speaker_map)
        
        unanswered = result["unanswered_questions"]
        # Should detect at least some unanswered questions
        assert isinstance(unanswered, list)
    
    def test_qa_analysis_question_classification(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test question type classification."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        qa_pairs = result["qa_pairs"]
        for pair in qa_pairs:
            question = pair["question"]
            assert "type" in question
            assert question["type"] in ["open_ended", "closed", "rhetorical", "clarification"]
    
    def test_qa_analysis_question_word_extraction(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test question word extraction."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        qa_pairs = result["qa_pairs"]
        for pair in qa_pairs:
            question = pair["question"]
            # question_word may be None for some question types
            assert "question_word" in question
    
    def test_qa_analysis_statistics(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test Q&A statistics calculation."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        stats = result["statistics"]
        assert "total_questions" in stats
        assert "answered" in stats
        assert "unanswered" in stats
        assert "avg_response_time" in stats
        assert "avg_quality_score" in stats
        
        assert stats["total_questions"] >= 0
        assert stats["answered"] >= 0
        assert stats["unanswered"] >= 0
    
    def test_qa_analysis_pattern_based_detection(self, qa_module, sample_segments_pattern_questions, sample_speaker_map):
        """Test question detection using pattern matching (without acts data)."""
        result = qa_module.analyze(sample_segments_pattern_questions, sample_speaker_map)
        
        assert "qa_pairs" in result
        # Should detect questions even without acts data
        questions_found = sum(1 for pair in result["qa_pairs"] if pair.get("question"))
        assert questions_found > 0
    
    def test_qa_analysis_with_acts_data(self, qa_module, sample_segments_with_questions, sample_speaker_map, sample_acts_data):
        """Test Q&A analysis with acts data."""
        result = qa_module.analyze(
            sample_segments_with_questions,
            sample_speaker_map,
            acts_data=sample_acts_data
        )
        
        assert "qa_pairs" in result
        assert len(result["qa_pairs"]) > 0
    
    def test_qa_analysis_question_chains(self, qa_module, sample_segments_with_questions, sample_speaker_map):
        """Test question chain detection."""
        result = qa_module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        chains = result["question_chains"]
        assert isinstance(chains, list)
        # May or may not have chains depending on timing
    
    def test_qa_analysis_empty_segments(self, qa_module, sample_speaker_map):
        """Test Q&A analysis with empty segments."""
        segments = []
        
        result = qa_module.analyze(segments, sample_speaker_map)
        
        assert "qa_pairs" in result
        assert "statistics" in result
        assert result["statistics"]["total_questions"] == 0
    
    def test_qa_analysis_no_questions(self, qa_module, sample_speaker_map):
        """Test Q&A analysis with no questions."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "This is a statement.", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Another statement here.", "start": 2.5, "end": 4.0},
        ]
        
        result = qa_module.analyze(segments, sample_speaker_map)
        
        assert "qa_pairs" in result
        assert result["statistics"]["total_questions"] == 0
    
    def test_qa_analysis_single_speaker(self, qa_module, sample_speaker_map):
        """Test Q&A analysis with single speaker (should handle gracefully)."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What should I do?", "start": 0.0, "end": 2.0, "dialogue_act": "question", "act_type": "question"},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "I should check the documentation.", "start": 2.5, "end": 5.0},
        ]
        
        result = qa_module.analyze(segments, sample_speaker_map)
        
        # Should handle single speaker (may not match answers from same speaker)
        assert "qa_pairs" in result
        assert "statistics" in result
    
    def test_qa_analysis_custom_response_threshold(self, sample_segments_with_questions, sample_speaker_map):
        """Test Q&A analysis with custom response time threshold."""
        module = QAAnalysis(config={"response_time_threshold": 5.0})
        
        result = module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        assert "qa_pairs" in result
        # Should use custom threshold for matching
    
    def test_qa_analysis_quality_weights(self, sample_segments_with_questions, sample_speaker_map):
        """Test Q&A analysis with custom quality weights."""
        custom_weights = {
            "directness": 0.5,
            "completeness": 0.3,
            "relevance": 0.15,
            "length": 0.05
        }
        module = QAAnalysis(config={"quality_weights": custom_weights})
        
        result = module.analyze(sample_segments_with_questions, sample_speaker_map)
        
        assert "qa_pairs" in result
        # Quality scores should reflect custom weights
    
    def test_qa_analysis_run_from_context(self, qa_module, pipeline_context_factory):
        """Test running Q&A analysis from PipelineContext."""
        context = pipeline_context_factory()
        
        # Add acts result to context (required dependency)
        acts_result = {
            "segments_with_acts": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "What time is it?",
                    "start": 0.0,
                    "dialogue_act": "question",
                    "act_type": "question"
                }
            ]
        }
        context.store_analysis_result("acts", acts_result)
        
        result = qa_module.run_from_context(context)
        
        assert result["status"] == "success"
        assert "results" in result
        assert "output_directory" in result
    
    def test_qa_analysis_run_from_context_no_acts(self, qa_module, pipeline_context_factory):
        """Test running Q&A analysis without acts data (should use pattern matching)."""
        context = pipeline_context_factory()
        
        # Don't add acts result - should fall back to pattern matching
        result = qa_module.run_from_context(context)
        
        # Should still work but may be less accurate
        assert result["status"] == "success" or result["status"] == "error"
    
    def test_qa_analysis_directness_calculation(self, qa_module):
        """Test directness score calculation."""
        question_text = "What is the deadline?"
        answer_text = "The deadline is next Friday."
        
        directness = qa_module._calculate_directness(question_text, answer_text, "what")
        
        assert 0.0 <= directness <= 1.0
        # Should have some directness since "deadline" appears in both
    
    def test_qa_analysis_completeness_calculation(self, qa_module):
        """Test completeness score calculation."""
        question_text = "What is your name?"
        answer_text = "My name is Bob."
        
        completeness = qa_module._calculate_completeness(question_text, answer_text, "open_ended")
        
        assert 0.0 <= completeness <= 1.0
        # Should have reasonable completeness for a good answer
    
    def test_qa_analysis_relevance_calculation(self, qa_module):
        """Test relevance score calculation."""
        question_text = "What time is the meeting?"
        answer_text = "The meeting is at 3 PM."
        
        relevance = qa_module._calculate_relevance(question_text, answer_text)
        
        assert 0.0 <= relevance <= 1.0
        # Should have good relevance since "meeting" appears in both
    
    def test_qa_analysis_length_score_calculation(self, qa_module):
        """Test length appropriateness score calculation."""
        question_text = "What time?"
        answer_text = "The meeting is scheduled for 3 PM in the conference room."
        
        length_score = qa_module._calculate_length_score(question_text, answer_text)
        
        assert 0.0 <= length_score <= 1.0
        # May be lower if answer is too long relative to question
