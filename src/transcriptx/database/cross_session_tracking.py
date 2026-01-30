"""
Cross-session speaker tracking and fingerprinting for TranscriptX.

This module provides advanced speaker tracking capabilities across multiple
conversations and sessions, including speaker matching, pattern evolution
tracking, and behavioral anomaly detection.

Key Features:
- Cross-session speaker matching and identification
- Behavioral pattern evolution tracking
- Speaker clustering and grouping
- Anomaly detection and alerting
- Confidence scoring and verification
- Network analysis and interaction mapping

The system is designed to:
- Track speakers across multiple conversations
- Identify behavioral patterns and changes
- Group similar speakers for analysis
- Detect unusual behavior patterns
- Provide confidence scores for matches
- Support manual verification and correction
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session as DBSession

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import (
    Speaker,
    SpeakerCluster,
    SpeakerClusterMember,
    SpeakerLink,
    SpeakerSession,
    PatternEvolution,
    BehavioralAnomaly,
    BehavioralFingerprint,
)
from transcriptx.database.database import get_session
from transcriptx.database.speaker_profiling import SpeakerProfilingService

logger = get_logger()


class CrossSessionTrackingService:
    """
    Advanced cross-session speaker tracking service.

    This service provides comprehensive speaker tracking capabilities
    across multiple conversations and sessions, including matching,
    clustering, and pattern evolution tracking.
    """

    def __init__(self):
        """Initialize the cross-session tracking service."""
        self.profiling_service = SpeakerProfilingService()
        self.logger = get_logger()

    def find_speaker_matches(
        self,
        speaker_name: str,
        session_data: List[Dict[str, Any]],
        confidence_threshold: float = 0.7,
    ) -> List[Tuple[Speaker, float]]:
        """
        Find potential matches for a speaker across all sessions.

        Args:
            speaker_name: Name of the speaker to match
            session_data: Session data containing speaker segments
            confidence_threshold: Minimum confidence score for matches

        Returns:
            List of (speaker, confidence_score) tuples
        """
        with get_session() as session:
            # Generate behavioral fingerprint for the new speaker
            fingerprint = self._generate_session_fingerprint(session_data)

            # Find potential matches based on name similarity
            name_matches = self._find_name_matches(session, speaker_name)

            # Find behavioral matches
            behavioral_matches = self._find_behavioral_matches(session, fingerprint)

            # Combine and rank matches
            all_matches = self._combine_matches(name_matches, behavioral_matches)

            # Filter by confidence threshold
            filtered_matches = [
                (speaker, confidence)
                for speaker, confidence in all_matches
                if confidence >= confidence_threshold
            ]

            return filtered_matches

    def create_speaker_link(
        self,
        source_speaker_id: int,
        target_speaker_id: int,
        link_type: str = "fuzzy_match",
        confidence_score: float = 0.8,
        evidence_data: Optional[Dict[str, Any]] = None,
    ) -> SpeakerLink:
        """
        Create a link between two speakers across sessions.

        Args:
            source_speaker_id: ID of the source speaker
            target_speaker_id: ID of the target speaker
            link_type: Type of link (exact_match, fuzzy_match, manual_link)
            confidence_score: Confidence in the link
            evidence_data: Supporting evidence for the link

        Returns:
            Created speaker link
        """
        with get_session() as session:
            # Check if link already exists
            existing_link = (
                session.query(SpeakerLink)
                .filter(
                    SpeakerLink.source_speaker_id == source_speaker_id,
                    SpeakerLink.target_speaker_id == target_speaker_id,
                    SpeakerLink.is_active == True,
                )
                .first()
            )

            if existing_link:
                # Update existing link
                existing_link.confidence_score = confidence_score
                existing_link.link_type = link_type
                existing_link.evidence_data = evidence_data or {}
                existing_link.updated_at = datetime.now()
                session.commit()
                return existing_link

            # Create new link
            link = SpeakerLink(
                source_speaker_id=source_speaker_id,
                target_speaker_id=target_speaker_id,
                link_type=link_type,
                confidence_score=confidence_score,
                evidence_data=evidence_data or {},
                verification_status="pending",
            )

            session.add(link)
            session.commit()
            session.refresh(link)

            self.logger.info(
                f"Created speaker link: {source_speaker_id} -> {target_speaker_id} (confidence: {confidence_score})"
            )
            return link

    def track_speaker_evolution(
        self, speaker_id: int, session_data: List[Dict[str, Any]], session_id: int
    ) -> List[PatternEvolution]:
        """
        Track how a speaker's behavioral patterns evolve over time.

        Args:
            speaker_id: ID of the speaker to track
            session_data: New session data
            session_id: ID of the current session

        Returns:
            List of detected pattern evolutions
        """
        with get_session() as session:
            # Get speaker's current fingerprint
            current_fingerprint = (
                session.query(BehavioralFingerprint)
                .filter(
                    BehavioralFingerprint.speaker_id == speaker_id,
                    BehavioralFingerprint.is_current == True,
                )
                .first()
            )

            if not current_fingerprint:
                return []

            # Generate new fingerprint from session data
            new_fingerprint = self._generate_session_fingerprint(session_data)

            # Compare patterns and detect changes
            evolutions = []

            # Check vocabulary patterns
            vocab_evolution = self._detect_vocabulary_evolution(
                current_fingerprint.vocabulary_fingerprint,
                new_fingerprint.get("vocabulary_patterns", {}),
            )
            if vocab_evolution:
                evolutions.append(vocab_evolution)

            # Check speech rhythm patterns
            rhythm_evolution = self._detect_speech_rhythm_evolution(
                current_fingerprint.speech_rhythm,
                new_fingerprint.get("speech_patterns", {}),
            )
            if rhythm_evolution:
                evolutions.append(rhythm_evolution)

            # Check emotion patterns
            emotion_evolution = self._detect_emotion_evolution(
                current_fingerprint.emotion_signature,
                new_fingerprint.get("emotion_patterns", {}),
            )
            if emotion_evolution:
                evolutions.append(emotion_evolution)

            # Save evolutions to database
            for evolution in evolutions:
                evolution.speaker_id = speaker_id
                session.add(evolution)

            session.commit()

            self.logger.info(
                f"Tracked {len(evolutions)} pattern evolutions for speaker {speaker_id}"
            )
            return evolutions

    def detect_behavioral_anomalies(
        self, speaker_id: int, session_id: int, session_data: List[Dict[str, Any]]
    ) -> List[BehavioralAnomaly]:
        """
        Detect unusual behavioral patterns in a speaker's session.

        Args:
            speaker_id: ID of the speaker to analyze
            session_id: ID of the session being analyzed
            session_data: Session data to analyze

        Returns:
            List of detected behavioral anomalies
        """
        with get_session() as session:
            # Get speaker's historical patterns
            historical_patterns = self._get_historical_patterns(session, speaker_id)

            # Analyze current session
            current_patterns = self._analyze_session_patterns(session_data)

            # Detect anomalies
            anomalies = []

            # Check for unusual speech rate
            speech_rate_anomaly = self._detect_speech_rate_anomaly(
                historical_patterns.get("speech_rate", {}),
                current_patterns.get("speech_rate", {}),
            )
            if speech_rate_anomaly:
                anomalies.append(speech_rate_anomaly)

            # Check for vocabulary changes
            vocabulary_anomaly = self._detect_vocabulary_anomaly(
                historical_patterns.get("vocabulary", {}),
                current_patterns.get("vocabulary", {}),
            )
            if vocabulary_anomaly:
                anomalies.append(vocabulary_anomaly)

            # Check for emotion shifts
            emotion_anomaly = self._detect_emotion_anomaly(
                historical_patterns.get("emotion", {}),
                current_patterns.get("emotion", {}),
            )
            if emotion_anomaly:
                anomalies.append(emotion_anomaly)

            # Save anomalies to database
            for anomaly in anomalies:
                anomaly.speaker_id = speaker_id
                anomaly.session_id = session_id
                session.add(anomaly)

            session.commit()

            self.logger.info(
                f"Detected {len(anomalies)} behavioral anomalies for speaker {speaker_id}"
            )
            return anomalies

    def create_speaker_cluster(
        self,
        name: str,
        description: Optional[str] = None,
        cluster_type: str = "behavioral",
    ) -> SpeakerCluster:
        """
        Create a new speaker cluster for grouping similar speakers.

        Args:
            name: Name of the cluster
            description: Description of the cluster
            cluster_type: Type of cluster (behavioral, organizational, manual)

        Returns:
            Created speaker cluster
        """
        with get_session() as session:
            cluster = SpeakerCluster(
                name=name, description=description, cluster_type=cluster_type
            )

            session.add(cluster)
            session.commit()

            self.logger.info(f"Created speaker cluster: {name} (type: {cluster_type})")
            return cluster

    def add_speaker_to_cluster(
        self,
        speaker_id: int,
        cluster_id: int,
        confidence_score: float = 0.8,
        membership_type: str = "automatic",
    ) -> SpeakerClusterMember:
        """
        Add a speaker to a cluster.

        Args:
            speaker_id: ID of the speaker to add
            cluster_id: ID of the cluster to add to
            confidence_score: Confidence in the membership
            membership_type: Type of membership (automatic, manual, suggested)

        Returns:
            Created cluster membership
        """
        with get_session() as session:
            # Check if membership already exists
            existing_membership = (
                session.query(SpeakerClusterMember)
                .filter(
                    SpeakerClusterMember.speaker_id == speaker_id,
                    SpeakerClusterMember.cluster_id == cluster_id,
                )
                .first()
            )

            if existing_membership:
                # Update existing membership
                existing_membership.confidence_score = confidence_score
                existing_membership.membership_type = membership_type
                existing_membership.updated_at = datetime.now()
                session.commit()
                return existing_membership

            # Create new membership
            membership = SpeakerClusterMember(
                speaker_id=speaker_id,
                cluster_id=cluster_id,
                confidence_score=confidence_score,
                membership_type=membership_type,
            )

            session.add(membership)

            # Update cluster member count
            cluster = (
                session.query(SpeakerCluster)
                .filter(SpeakerCluster.id == cluster_id)
                .first()
            )
            if cluster:
                cluster.member_count += 1
                cluster.updated_at = datetime.now()

            session.commit()

            self.logger.info(f"Added speaker {speaker_id} to cluster {cluster_id}")
            return membership

    def get_speaker_network(
        self, speaker_id: int, max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get the interaction network for a speaker.

        Args:
            speaker_id: ID of the speaker
            max_depth: Maximum depth of network exploration

        Returns:
            Network data including connected speakers and interaction patterns
        """
        with get_session() as session:
            # Get direct links
            direct_links = (
                session.query(SpeakerLink)
                .filter(
                    (SpeakerLink.source_speaker_id == speaker_id)
                    | (SpeakerLink.target_speaker_id == speaker_id),
                    SpeakerLink.is_active == True,
                )
                .all()
            )

            # Get session participations
            participations = (
                session.query(SpeakerSession)
                .filter(SpeakerSession.speaker_id == speaker_id)
                .all()
            )

            # Build network data
            network = {
                "speaker_id": speaker_id,
                "direct_links": [
                    {
                        "link_id": link.id,
                        "linked_speaker_id": (
                            link.target_speaker_id
                            if link.source_speaker_id == speaker_id
                            else link.source_speaker_id
                        ),
                        "confidence": link.confidence_score,
                        "link_type": link.link_type,
                    }
                    for link in direct_links
                ],
                "session_participations": [
                    {
                        "session_id": participation.session_id,
                        "participation_score": participation.participation_score,
                        "behavioral_consistency": participation.behavioral_consistency,
                    }
                    for participation in participations
                ],
                "network_metrics": self._calculate_network_metrics(session, speaker_id),
            }

            return network

    def _generate_session_fingerprint(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a behavioral fingerprint from session data."""
        # This is a simplified implementation
        # In practice, this would use more sophisticated pattern recognition

        fingerprint = {
            "vocabulary_patterns": self._extract_vocabulary_patterns(session_data),
            "speech_patterns": self._extract_speech_patterns(session_data),
            "emotion_patterns": self._extract_emotion_patterns(session_data),
            "interaction_patterns": self._extract_interaction_patterns(session_data),
        }

        return fingerprint

    def _find_name_matches(
        self, session: DBSession, speaker_name: str
    ) -> List[Tuple[Speaker, float]]:
        """Find speakers with similar names."""
        # Normalize speaker name
        normalized_name = self._normalize_name(speaker_name)

        # Find exact matches
        exact_matches = (
            session.query(Speaker)
            .filter(Speaker.name.ilike(f"%{normalized_name}%"))
            .all()
        )

        # Find fuzzy matches
        fuzzy_matches = (
            session.query(Speaker).filter(Speaker.name.ilike(f"%{speaker_name}%")).all()
        )

        matches = []

        # Add exact matches with high confidence
        for speaker in exact_matches:
            confidence = self._calculate_name_similarity(speaker_name, speaker.name)
            matches.append((speaker, confidence))

        # Add fuzzy matches with lower confidence
        for speaker in fuzzy_matches:
            if speaker not in [m[0] for m in matches]:
                confidence = (
                    self._calculate_name_similarity(speaker_name, speaker.name) * 0.8
                )
                matches.append((speaker, confidence))

        return matches

    def _find_behavioral_matches(
        self, session: DBSession, fingerprint: Dict[str, Any]
    ) -> List[Tuple[Speaker, float]]:
        """Find speakers with similar behavioral patterns."""
        # Get all current fingerprints
        fingerprints = (
            session.query(BehavioralFingerprint)
            .filter(BehavioralFingerprint.is_current == True)
            .all()
        )

        matches = []

        for fp in fingerprints:
            confidence = self._calculate_behavioral_similarity(
                fingerprint, fp.fingerprint_data
            )
            if confidence > 0.5:  # Minimum threshold for behavioral matching
                speaker = (
                    session.query(Speaker).filter(Speaker.id == fp.speaker_id).first()
                )
                if speaker:
                    matches.append((speaker, confidence))

        return matches

    def _combine_matches(
        self,
        name_matches: List[Tuple[Speaker, float]],
        behavioral_matches: List[Tuple[Speaker, float]],
    ) -> List[Tuple[Speaker, float]]:
        """Combine name and behavioral matches with weighted scoring."""
        all_matches = {}

        # Add name matches
        for speaker, confidence in name_matches:
            all_matches[speaker.id] = {
                "speaker": speaker,
                "name_confidence": confidence,
                "behavioral_confidence": 0.0,
            }

        # Add behavioral matches
        for speaker, confidence in behavioral_matches:
            if speaker.id in all_matches:
                all_matches[speaker.id]["behavioral_confidence"] = confidence
            else:
                all_matches[speaker.id] = {
                    "speaker": speaker,
                    "name_confidence": 0.0,
                    "behavioral_confidence": confidence,
                }

        # Calculate combined confidence scores
        combined_matches = []
        for match_data in all_matches.values():
            # Weight name matching higher than behavioral matching
            combined_confidence = (
                match_data["name_confidence"] * 0.7
                + match_data["behavioral_confidence"] * 0.3
            )
            combined_matches.append((match_data["speaker"], combined_confidence))

        # Sort by confidence score
        combined_matches.sort(key=lambda x: x[1], reverse=True)

        return combined_matches

    def _normalize_name(self, name: str) -> str:
        """Normalize a speaker name for comparison."""
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r"\s+", " ", name.strip().lower())
        return normalized

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        # Simple implementation - in practice, use more sophisticated algorithms
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        if norm1 == norm2:
            return 1.0

        # Calculate Jaccard similarity
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        if union == 0:
            return 0.0

        return intersection / union

    def _calculate_behavioral_similarity(
        self, fingerprint1: Dict[str, Any], fingerprint2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two behavioral fingerprints."""
        # Simplified implementation
        # In practice, use more sophisticated pattern matching algorithms

        similarities = []

        # Compare vocabulary patterns
        if (
            "vocabulary_patterns" in fingerprint1
            and "vocabulary_fingerprint" in fingerprint2
        ):
            vocab_sim = self._compare_vocabulary_patterns(
                fingerprint1["vocabulary_patterns"],
                fingerprint2["vocabulary_fingerprint"],
            )
            similarities.append(vocab_sim)

        # Compare speech patterns
        if "speech_patterns" in fingerprint1 and "speech_rhythm" in fingerprint2:
            speech_sim = self._compare_speech_patterns(
                fingerprint1["speech_patterns"], fingerprint2["speech_rhythm"]
            )
            similarities.append(speech_sim)

        # Compare emotion patterns
        if "emotion_patterns" in fingerprint1 and "emotion_signature" in fingerprint2:
            emotion_sim = self._compare_emotion_patterns(
                fingerprint1["emotion_patterns"], fingerprint2["emotion_signature"]
            )
            similarities.append(emotion_sim)

        if not similarities:
            return 0.0

        # Return average similarity
        return sum(similarities) / len(similarities)

    def _compare_vocabulary_patterns(
        self, patterns1: Dict[str, Any], patterns2: Dict[str, Any]
    ) -> float:
        """Compare vocabulary patterns between two fingerprints."""
        # Simplified implementation
        # In practice, use TF-IDF or other text similarity measures

        words1 = set(patterns1.get("common_words", []))
        words2 = set(patterns2.get("common_words", []))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _compare_speech_patterns(
        self, patterns1: Dict[str, Any], patterns2: Dict[str, Any]
    ) -> float:
        """Compare speech patterns between two fingerprints."""
        # Simplified implementation
        # In practice, use more sophisticated speech analysis

        rate1 = patterns1.get("average_speaking_rate", 0)
        rate2 = patterns2.get("average_speaking_rate", 0)

        if rate1 == 0 or rate2 == 0:
            return 0.0

        # Calculate similarity based on speaking rate
        rate_diff = abs(rate1 - rate2)
        max_rate = max(rate1, rate2)

        return max(0, 1 - (rate_diff / max_rate))

    def _compare_emotion_patterns(
        self, patterns1: Dict[str, Any], patterns2: Dict[str, Any]
    ) -> float:
        """Compare emotion patterns between two fingerprints."""
        # Simplified implementation
        # In practice, use more sophisticated emotion analysis

        emotions1 = patterns1.get("dominant_emotions", {})
        emotions2 = patterns2.get("dominant_emotions", {})

        if not emotions1 or not emotions2:
            return 0.0

        # Calculate cosine similarity between emotion vectors
        all_emotions = set(emotions1.keys()).union(set(emotions2.keys()))

        if not all_emotions:
            return 0.0

        dot_product = sum(
            emotions1.get(e, 0) * emotions2.get(e, 0) for e in all_emotions
        )
        norm1 = sum(emotions1.get(e, 0) ** 2 for e in all_emotions) ** 0.5
        norm2 = sum(emotions2.get(e, 0) ** 2 for e in all_emotions) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _extract_vocabulary_patterns(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract vocabulary patterns from session data."""
        # Simplified implementation
        all_text = " ".join([segment.get("text", "") for segment in session_data])
        words = re.findall(r"\b\w+\b", all_text.lower())

        # Count word frequencies
        word_freq = {}
        for word in words:
            if len(word) > 2:  # Skip very short words
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get most common words
        common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            "common_words": [word for word, freq in common_words],
            "word_frequencies": dict(common_words),
            "total_words": len(words),
            "unique_words": len(word_freq),
        }

    def _extract_speech_patterns(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract speech patterns from session data."""
        if not session_data:
            return {}

        # Calculate speaking rate
        total_duration = sum(
            segment.get("end", 0) - segment.get("start", 0) for segment in session_data
        )

        total_words = sum(
            len(segment.get("text", "").split()) for segment in session_data
        )

        speaking_rate = total_words / total_duration if total_duration > 0 else 0

        return {
            "average_speaking_rate": speaking_rate,
            "total_duration": total_duration,
            "total_words": total_words,
            "segment_count": len(session_data),
        }

    def _extract_emotion_patterns(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract emotion patterns from session data."""
        # Simplified implementation
        # In practice, use emotion analysis models

        emotions = {"positive": 0.3, "negative": 0.2, "neutral": 0.5}

        return {
            "dominant_emotions": emotions,
            "emotion_distribution": emotions,
            "dominant_emotion": "neutral",
        }

    def _extract_interaction_patterns(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract interaction patterns from session data."""
        # Simplified implementation
        # In practice, analyze turn-taking, interruptions, etc.

        return {
            "turn_taking_pattern": "normal",
            "interruption_frequency": 0.1,
            "response_style": "direct",
        }

    def _detect_vocabulary_evolution(
        self, old_patterns: Dict[str, Any], new_patterns: Dict[str, Any]
    ) -> Optional[PatternEvolution]:
        """Detect vocabulary pattern evolution."""
        if not old_patterns or not new_patterns:
            return None

        # Compare vocabulary patterns
        old_words = set(old_patterns.get("common_words", []))
        new_words = set(new_patterns.get("common_words", []))

        new_vocab = new_words - old_words
        lost_vocab = old_words - new_words

        if not new_vocab and not lost_vocab:
            return None

        change_magnitude = len(new_vocab) + len(lost_vocab)
        change_confidence = min(1.0, change_magnitude / 10.0)  # Normalize

        return PatternEvolution(
            pattern_type="vocabulary",
            old_value=old_patterns,
            new_value=new_patterns,
            change_confidence=change_confidence,
            change_magnitude=change_magnitude,
            change_reason="Vocabulary evolution detected",
            is_significant=change_magnitude > 5,
        )

    def _detect_speech_rhythm_evolution(
        self, old_patterns: Dict[str, Any], new_patterns: Dict[str, Any]
    ) -> Optional[PatternEvolution]:
        """Detect speech rhythm evolution."""
        if not old_patterns or not new_patterns:
            return None

        old_rate = old_patterns.get("average_speaking_rate", 0)
        new_rate = new_patterns.get("average_speaking_rate", 0)

        if old_rate == 0 or new_rate == 0:
            return None

        rate_change = abs(new_rate - old_rate) / old_rate
        change_confidence = min(1.0, rate_change)

        if rate_change < 0.1:  # Less than 10% change
            return None

        return PatternEvolution(
            pattern_type="speech_rhythm",
            old_value=old_patterns,
            new_value=new_patterns,
            change_confidence=change_confidence,
            change_magnitude=rate_change,
            change_reason="Speech rate change detected",
            is_significant=rate_change > 0.2,
        )

    def _detect_emotion_evolution(
        self, old_patterns: Dict[str, Any], new_patterns: Dict[str, Any]
    ) -> Optional[PatternEvolution]:
        """Detect emotion pattern evolution."""
        if not old_patterns or not new_patterns:
            return None

        old_emotions = old_patterns.get("dominant_emotions", {})
        new_emotions = new_patterns.get("dominant_emotions", {})

        if not old_emotions or not new_emotions:
            return None

        # Calculate emotion change
        all_emotions = set(old_emotions.keys()).union(set(new_emotions.keys()))
        emotion_change = sum(
            abs(new_emotions.get(e, 0) - old_emotions.get(e, 0)) for e in all_emotions
        )

        change_confidence = min(1.0, emotion_change)

        if emotion_change < 0.1:  # Less than 10% change
            return None

        return PatternEvolution(
            pattern_type="emotion",
            old_value=old_patterns,
            new_value=new_patterns,
            change_confidence=change_confidence,
            change_magnitude=emotion_change,
            change_reason="Emotion pattern change detected",
            is_significant=emotion_change > 0.3,
        )

    def _get_historical_patterns(
        self, session: DBSession, speaker_id: int
    ) -> Dict[str, Any]:
        """Get historical behavioral patterns for a speaker."""
        # Get recent fingerprints
        recent_fingerprints = (
            session.query(BehavioralFingerprint)
            .filter(BehavioralFingerprint.speaker_id == speaker_id)
            .order_by(BehavioralFingerprint.created_at.desc())
            .limit(5)
            .all()
        )

        if not recent_fingerprints:
            return {}

        # Aggregate patterns
        aggregated = {"speech_rate": [], "vocabulary": [], "emotion": []}

        for fp in recent_fingerprints:
            if fp.speech_rhythm:
                aggregated["speech_rate"].append(fp.speech_rhythm)
            if fp.vocabulary_fingerprint:
                aggregated["vocabulary"].append(fp.vocabulary_fingerprint)
            if fp.emotion_signature:
                aggregated["emotion"].append(fp.emotion_signature)

        # Calculate averages
        patterns = {}
        for pattern_type, values in aggregated.items():
            if values:
                if pattern_type == "speech_rate":
                    patterns[pattern_type] = {
                        "average_speaking_rate": sum(
                            v.get("average_speaking_rate", 0) for v in values
                        )
                        / len(values)
                    }
                else:
                    patterns[pattern_type] = values[0]  # Use most recent

        return patterns

    def _analyze_session_patterns(
        self, session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze patterns in session data."""
        return {
            "speech_rate": self._extract_speech_patterns(session_data),
            "vocabulary": self._extract_vocabulary_patterns(session_data),
            "emotion": self._extract_emotion_patterns(session_data),
        }

    def _detect_speech_rate_anomaly(
        self, historical_patterns: Dict[str, Any], current_patterns: Dict[str, Any]
    ) -> Optional[BehavioralAnomaly]:
        """Detect unusual speech rate patterns."""
        if not historical_patterns or not current_patterns:
            return None

        historical_rate = historical_patterns.get("average_speaking_rate", 0)
        current_rate = current_patterns.get("average_speaking_rate", 0)

        if historical_rate == 0:
            return None

        rate_change = abs(current_rate - historical_rate) / historical_rate

        if rate_change > 0.5:  # More than 50% change
            severity = min(1.0, rate_change)
            return BehavioralAnomaly(
                anomaly_type="unusual_speech_rate",
                severity=severity,
                description=f"Speech rate changed by {rate_change:.1%}",
                evidence_data={
                    "historical_rate": historical_rate,
                    "current_rate": current_rate,
                    "rate_change": rate_change,
                },
            )

        return None

    def _detect_vocabulary_anomaly(
        self, historical_patterns: Dict[str, Any], current_patterns: Dict[str, Any]
    ) -> Optional[BehavioralAnomaly]:
        """Detect unusual vocabulary patterns."""
        if not historical_patterns or not current_patterns:
            return None

        historical_words = set(historical_patterns.get("common_words", []))
        current_words = set(current_patterns.get("common_words", []))

        new_words = current_words - historical_words
        lost_words = historical_words - current_words

        total_change = len(new_words) + len(lost_words)

        if total_change > 5:  # More than 5 word changes
            severity = min(1.0, total_change / 10.0)
            return BehavioralAnomaly(
                anomaly_type="vocabulary_change",
                severity=severity,
                description=f"Vocabulary changed by {total_change} words",
                evidence_data={
                    "new_words": list(new_words),
                    "lost_words": list(lost_words),
                    "total_change": total_change,
                },
            )

        return None

    def _detect_emotion_anomaly(
        self, historical_patterns: Dict[str, Any], current_patterns: Dict[str, Any]
    ) -> Optional[BehavioralAnomaly]:
        """Detect unusual emotion patterns."""
        if not historical_patterns or not current_patterns:
            return None

        historical_emotions = historical_patterns.get("dominant_emotions", {})
        current_emotions = current_patterns.get("dominant_emotions", {})

        if not historical_emotions or not current_emotions:
            return None

        # Calculate emotion change
        all_emotions = set(historical_emotions.keys()).union(
            set(current_emotions.keys())
        )
        emotion_change = sum(
            abs(current_emotions.get(e, 0) - historical_emotions.get(e, 0))
            for e in all_emotions
        )

        if emotion_change > 0.5:  # More than 50% emotion change
            severity = min(1.0, emotion_change)
            return BehavioralAnomaly(
                anomaly_type="emotion_shift",
                severity=severity,
                description=f"Emotion pattern shifted by {emotion_change:.1%}",
                evidence_data={
                    "historical_emotions": historical_emotions,
                    "current_emotions": current_emotions,
                    "emotion_change": emotion_change,
                },
            )

        return None

    def _calculate_network_metrics(
        self, session: DBSession, speaker_id: int
    ) -> Dict[str, Any]:
        """Calculate network metrics for a speaker."""
        # Get all links for this speaker
        links = (
            session.query(SpeakerLink)
            .filter(
                (SpeakerLink.source_speaker_id == speaker_id)
                | (SpeakerLink.target_speaker_id == speaker_id),
                SpeakerLink.is_active == True,
            )
            .all()
        )

        # Calculate metrics
        total_connections = len(links)
        high_confidence_connections = len(
            [link for link in links if link.confidence_score > 0.8]
        )

        return {
            "total_connections": total_connections,
            "high_confidence_connections": high_confidence_connections,
            "average_confidence": (
                sum(link.confidence_score for link in links) / len(links)
                if links
                else 0.0
            ),
        }
