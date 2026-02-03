"""
Semantic similarity data extractor for TranscriptX.

This module extracts semantic similarity data from analysis results and
transforms it for database storage using the shared base extractor.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from transcriptx.core.data_extraction.base_extractor import BaseDataExtractor
from transcriptx.core.utils.similarity_utils import similarity_calculator


class SemanticDataExtractor(BaseDataExtractor):
    """
    Data extractor for semantic similarity analysis results.

    This extractor processes semantic similarity analysis results and extracts
    speaker-level data including repetition patterns, similarity scores, and
    agreement/disagreement classifications.
    """

    def __init__(self):
        """Initialize the semantic data extractor."""
        super().__init__("semantic_similarity")

    def get_required_fields(self) -> List[str]:
        """Get list of required fields for semantic data."""
        return ["repetitions", "similarity_scores", "agreement_patterns"]

    def extract_data(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """
        Extract semantic similarity data for a specific speaker.

        Args:
            analysis_results: Complete semantic similarity analysis results
            speaker_id: Speaker identifier

        Returns:
            Extracted semantic data dictionary
        """
        try:
            extracted_data = {
                "repetitions": self._extract_repetitions(analysis_results, speaker_id),
                "similarity_scores": self._extract_similarity_scores(
                    analysis_results, speaker_id
                ),
                "agreement_patterns": self._extract_agreement_patterns(
                    analysis_results, speaker_id
                ),
                "vocabulary_patterns": self._extract_vocabulary_patterns(
                    analysis_results, speaker_id
                ),
                "semantic_consistency": self._calculate_semantic_consistency(
                    analysis_results, speaker_id
                ),
            }

            return extracted_data
        except Exception as e:
            self.logger.error(f"Failed to extract semantic data for {speaker_id}: {e}")
            return {
                "error": str(e),
                "speaker_id": speaker_id,
                "module": self.module_name,
            }

    def _extract_repetitions(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """Extract repetition data for a speaker."""
        try:
            speaker_repetitions = analysis_results.get("speaker_repetitions", {})
            speaker_reps = speaker_repetitions.get(speaker_id, [])

            if not speaker_reps:
                return {
                    "total_repetitions": 0,
                    "repetition_types": {},
                    "average_similarity": 0.0,
                    "repetition_frequency": 0.0,
                }

            # Analyze repetition types
            repetition_types = Counter()
            similarities = []

            for rep in speaker_reps:
                rep_type = rep.get("type", "unknown")
                repetition_types[rep_type] += 1

                similarity = rep.get("similarity", 0.0)
                similarities.append(similarity)

            return {
                "total_repetitions": len(speaker_reps),
                "repetition_types": dict(repetition_types),
                "average_similarity": (
                    float(sum(similarities) / len(similarities))
                    if similarities
                    else 0.0
                ),
                "repetition_frequency": len(speaker_reps)
                / max(1, len(analysis_results.get("segments", []))),
            }
        except Exception as e:
            self.logger.warning(f"Failed to extract repetitions for {speaker_id}: {e}")
            return {"error": str(e)}

    def _extract_similarity_scores(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """Extract similarity score data for a speaker."""
        try:
            # Get all similarity scores involving this speaker
            all_similarities = []

            # From speaker repetitions
            speaker_repetitions = analysis_results.get("speaker_repetitions", {})
            speaker_reps = speaker_repetitions.get(speaker_id, [])
            for rep in speaker_reps:
                all_similarities.append(rep.get("similarity", 0.0))

            # From cross-speaker repetitions
            cross_repetitions = analysis_results.get("cross_speaker_repetitions", [])
            for rep in cross_repetitions:
                if (
                    rep.get("segment1", {}).get("speaker") == speaker_id
                    or rep.get("segment2", {}).get("speaker") == speaker_id
                ):
                    all_similarities.append(rep.get("similarity", 0.0))

            if not all_similarities:
                return {
                    "total_comparisons": 0,
                    "average_similarity": 0.0,
                    "similarity_distribution": {},
                    "high_similarity_count": 0,
                }

            # Calculate statistics
            avg_similarity = sum(all_similarities) / len(all_similarities)
            high_similarity_count = sum(1 for s in all_similarities if s > 0.8)

            # Create distribution
            distribution = Counter()
            for score in all_similarities:
                bucket = int(score * 10) / 10  # Group into 0.1 buckets
                distribution[f"{bucket:.1f}"] += 1

            return {
                "total_comparisons": len(all_similarities),
                "average_similarity": float(avg_similarity),
                "similarity_distribution": dict(distribution),
                "high_similarity_count": high_similarity_count,
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to extract similarity scores for {speaker_id}: {e}"
            )
            return {"error": str(e)}

    def _extract_agreement_patterns(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """Extract agreement/disagreement patterns for a speaker."""
        try:
            cross_repetitions = analysis_results.get("cross_speaker_repetitions", [])

            agreements = []
            disagreements = []
            paraphrases = []

            for rep in cross_repetitions:
                if (
                    rep.get("segment1", {}).get("speaker") == speaker_id
                    or rep.get("segment2", {}).get("speaker") == speaker_id
                ):

                    agreement_type = rep.get("agreement_type", "neutral")

                    if agreement_type == "agreement":
                        agreements.append(rep.get("segment1", {}).get("text", ""))
                    elif agreement_type == "disagreement":
                        disagreements.append(rep.get("segment1", {}).get("text", ""))
                    elif agreement_type == "paraphrase":
                        paraphrases.append(rep.get("segment1", {}).get("text", ""))

            return {
                "agreement_count": len(agreements),
                "disagreement_count": len(disagreements),
                "paraphrase_count": len(paraphrases),
                "agreement_phrases": agreements[:10],  # Limit to first 10
                "disagreement_phrases": disagreements[:10],
                "paraphrase_phrases": paraphrases[:10],
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to extract agreement patterns for {speaker_id}: {e}"
            )
            return {"error": str(e)}

    def _extract_vocabulary_patterns(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """Extract vocabulary patterns for a speaker."""
        try:
            # Get all text from this speaker
            segments = analysis_results.get("segments", [])
            speaker_texts = []

            for segment in segments:
                if segment.get("speaker") == speaker_id:
                    text = segment.get("text", "")
                    if text.strip():
                        speaker_texts.append(text)

            if not speaker_texts:
                return {
                    "common_words": [],
                    "word_frequencies": {},
                    "total_words": 0,
                    "unique_words": 0,
                }

            # Use the shared vocabulary pattern extraction
            return similarity_calculator.extract_vocabulary_patterns(speaker_texts)
        except Exception as e:
            self.logger.warning(
                f"Failed to extract vocabulary patterns for {speaker_id}: {e}"
            )
            return {"error": str(e)}

    def _calculate_semantic_consistency(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Optional[float]:
        """Calculate semantic consistency score for a speaker."""
        try:
            # Get all text from this speaker
            segments = analysis_results.get("segments", [])
            speaker_texts = []

            for segment in segments:
                if segment.get("speaker") == speaker_id:
                    text = segment.get("text", "")
                    if text.strip():
                        speaker_texts.append(text)

            if len(speaker_texts) < 2:
                return None

            # Use the shared semantic consistency calculation
            return self._calculate_semantic_consistency_from_texts(speaker_texts)
        except Exception as e:
            self.logger.warning(
                f"Failed to calculate semantic consistency for {speaker_id}: {e}"
            )
            return None

    def _calculate_semantic_consistency_from_texts(
        self, texts: List[str]
    ) -> Optional[float]:
        """Calculate semantic consistency score from text samples."""
        if len(texts) < 2:
            return None

        # Use the shared similarity calculator for consistency
        total_similarity = 0.0
        comparisons = 0

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                similarity = similarity_calculator.calculate_text_similarity(
                    texts[i], texts[j], method="tfidf"
                )
                total_similarity += similarity
                comparisons += 1

        return total_similarity / comparisons if comparisons > 0 else None

    def _analyze_agreement_patterns(self, agreements: List[str]) -> Dict[str, Any]:
        """Analyze agreement patterns."""
        if not agreements:
            return {}

        counter = Counter(agreements)
        return {
            "agreement_types": dict(counter),
            "total_agreements": len(agreements),
            "unique_agreements": len(set(agreements)),
        }

    def _analyze_disagreement_patterns(
        self, disagreements: List[str]
    ) -> Dict[str, Any]:
        """Analyze disagreement patterns."""
        if not disagreements:
            return {}

        counter = Counter(disagreements)
        return {
            "disagreement_types": dict(counter),
            "total_disagreements": len(disagreements),
            "unique_disagreements": len(set(disagreements)),
        }
