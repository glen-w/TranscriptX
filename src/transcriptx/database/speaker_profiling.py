"""
Speaker profiling service for TranscriptX database.

This module provides comprehensive speaker profiling capabilities that integrate
with the database backend, including behavioral fingerprinting, profile management,
and cross-session speaker tracking.

Key Features:
- Behavioral fingerprinting and analysis
- Speaker profile creation and management
- Cross-session speaker tracking
- Behavioral pattern recognition
- Profile versioning and history
- Performance optimization and caching

The speaker profiling system provides:
- Persistent speaker profiles across sessions
- Behavioral fingerprinting for speaker identification
- Statistical analysis of speaking patterns
- Cross-session behavioral tracking
- Profile evolution and versioning
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.analysis.emotion import compute_nrc_emotions
from transcriptx.core.analysis.ner import extract_named_entities
from transcriptx.core.utils.nlp_utils import extract_tics_from_text
from transcriptx.core.analysis.sentiment import score_sentiment
from .database import get_session
from .repositories import SpeakerRepository, ProfileRepository

logger = get_logger()


class SpeakerProfilingService:
    """
    Comprehensive speaker profiling service.

    This service provides advanced speaker profiling capabilities including:
    - Behavioral fingerprinting
    - Profile creation and management
    - Cross-session tracking
    - Pattern recognition
    - Statistical analysis

    The service integrates with the database backend to provide:
    - Persistent speaker profiles
    - Behavioral data storage
    - Profile versioning
    - Cross-session analysis
    """

    _init_logged = False  # Log once per process to avoid duplicate lines

    def __init__(self):
        """Initialize the speaker profiling service."""
        self.session = get_session()
        self.speaker_repo = SpeakerRepository(self.session)
        self.profile_repo = ProfileRepository(self.session)

        if not SpeakerProfilingService._init_logged:
            logger.info("🔧 Initialized speaker profiling service")
            SpeakerProfilingService._init_logged = True

    def create_or_get_speaker(
        self,
        name: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        role: Optional[str] = None,
        color: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Tuple[Any, bool]:
        """
        Create a new speaker or get existing one.

        Args:
            name: Speaker name
            display_name: Display name (optional)
            email: Email address (optional)
            organization: Organization (optional)
            role: Role or title (optional)
            color: Hex color code (optional)
            avatar_url: Avatar URL (optional)

        Returns:
            Tuple of (speaker, is_new) where is_new indicates if speaker was created
        """
        try:
            # Check if speaker already exists
            existing_speaker = self.speaker_repo.get_speaker_by_name(name)
            if existing_speaker:
                logger.info(f"📋 Found existing speaker: {name}")
                return existing_speaker, False

            # Create new speaker
            speaker = self.speaker_repo.create_speaker(
                name=name,
                display_name=display_name,
                email=email,
                organization=organization,
                role=role,
                color=color,
                avatar_url=avatar_url,
            )

            logger.info(f"✅ Created new speaker: {name}")
            return speaker, True

        except Exception as e:
            logger.error(f"❌ Failed to create/get speaker {name}: {e}")
            raise

    def create_speaker_profile(
        self,
        speaker_id: int,
        segments_data: List[Dict[str, Any]],
        analysis_results: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Create a comprehensive speaker profile from session data.

        Args:
            speaker_id: Speaker ID
            segments_data: List of speaker segments with text and metadata
            analysis_results: Optional analysis results to incorporate

        Returns:
            Created speaker profile
        """
        try:
            logger.info(f"🔧 Creating profile for speaker {speaker_id}")

            # Extract text from segments
            texts = [segment.get("text", "") for segment in segments_data]
            combined_text = " ".join(texts)

            # Perform behavioral analysis
            behavioral_data = self._analyze_behavioral_patterns(
                segments_data, combined_text
            )

            # Create profile data
            profile_data = {
                "speaker_id": speaker_id,
                "created_at": datetime.utcnow().isoformat(),
                "session_count": 1,
                "total_segments": len(segments_data),
                "total_words": sum(len(text.split()) for text in texts),
                "behavioral_analysis": behavioral_data,
                "analysis_results": analysis_results or {},
            }

            # Create preferences and settings
            preferences = self._generate_preferences(behavioral_data)
            settings = self._generate_settings(behavioral_data)

            # Create profile
            profile = self.profile_repo.create_speaker_profile(
                speaker_id=speaker_id,
                profile_data=profile_data,
                preferences=preferences,
                settings=settings,
                vocabulary_patterns=behavioral_data.get("vocabulary_patterns", {}),
                speech_patterns=behavioral_data.get("speech_patterns", {}),
                emotion_patterns=behavioral_data.get("emotion_patterns", {}),
                session_history=[
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "segments_count": len(segments_data),
                        "word_count": profile_data["total_words"],
                    }
                ],
            )

            logger.info(f"✅ Created profile for speaker {speaker_id}")
            return profile

        except Exception as e:
            logger.error(f"❌ Failed to create profile for speaker {speaker_id}: {e}")
            raise

    def update_speaker_profile(
        self,
        speaker_id: int,
        segments_data: List[Dict[str, Any]],
        analysis_results: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Update existing speaker profile with new session data.

        Args:
            speaker_id: Speaker ID
            segments_data: List of speaker segments with text and metadata
            analysis_results: Optional analysis results to incorporate

        Returns:
            Updated speaker profile
        """
        try:
            logger.info(f"🔧 Updating profile for speaker {speaker_id}")

            # Get current profile
            current_profile = self.profile_repo.get_current_profile(speaker_id)
            if not current_profile:
                logger.warning(
                    f"⚠️ No current profile found for speaker {speaker_id}, creating new one"
                )
                return self.create_speaker_profile(
                    speaker_id, segments_data, analysis_results
                )

            # Extract text from segments
            texts = [segment.get("text", "") for segment in segments_data]
            combined_text = " ".join(texts)

            # Perform behavioral analysis
            behavioral_data = self._analyze_behavioral_patterns(
                segments_data, combined_text
            )

            # Update profile data
            profile_data = current_profile.profile_data.copy()
            profile_data["session_count"] += 1
            profile_data["total_segments"] += len(segments_data)
            profile_data["total_words"] += sum(len(text.split()) for text in texts)
            profile_data["last_updated"] = datetime.utcnow().isoformat()

            # Merge behavioral analysis
            self._merge_behavioral_data(
                profile_data["behavioral_analysis"], behavioral_data
            )

            # Update session history
            session_history = current_profile.session_history.copy()
            session_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "segments_count": len(segments_data),
                    "word_count": sum(len(text.split()) for text in texts),
                }
            )

            # Keep only last 50 sessions
            if len(session_history) > 50:
                session_history = session_history[-50:]

            # Create new profile version
            profile = self.profile_repo.create_speaker_profile(
                speaker_id=speaker_id,
                profile_data=profile_data,
                preferences=self._generate_preferences(
                    profile_data["behavioral_analysis"]
                ),
                settings=self._generate_settings(profile_data["behavioral_analysis"]),
                vocabulary_patterns=profile_data["behavioral_analysis"].get(
                    "vocabulary_patterns", {}
                ),
                speech_patterns=profile_data["behavioral_analysis"].get(
                    "speech_patterns", {}
                ),
                emotion_patterns=profile_data["behavioral_analysis"].get(
                    "emotion_patterns", {}
                ),
                session_history=session_history,
                analysis_history=current_profile.analysis_history
                + [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "analysis_results": analysis_results or {},
                    }
                ],
            )

            logger.info(f"✅ Updated profile for speaker {speaker_id}")
            return profile

        except Exception as e:
            logger.error(f"❌ Failed to update profile for speaker {speaker_id}: {e}")
            raise

    def create_behavioral_fingerprint(
        self, speaker_id: int, segments_data: List[Dict[str, Any]]
    ) -> Any:
        """
        Create a behavioral fingerprint for a speaker.

        Args:
            speaker_id: Speaker ID
            segments_data: List of speaker segments with text and metadata

        Returns:
            Created behavioral fingerprint
        """
        try:
            logger.info(f"🔧 Creating behavioral fingerprint for speaker {speaker_id}")

            # Extract text from segments
            texts = [segment.get("text", "") for segment in segments_data]
            combined_text = " ".join(texts)

            # Perform comprehensive behavioral analysis
            fingerprint_data = self._create_comprehensive_fingerprint(
                segments_data, combined_text
            )

            # Create fingerprint
            fingerprint = self.profile_repo.create_behavioral_fingerprint(
                speaker_id=speaker_id,
                fingerprint_data=fingerprint_data,
                vocabulary_fingerprint=fingerprint_data.get(
                    "vocabulary_fingerprint", {}
                ),
                speech_rhythm=fingerprint_data.get("speech_rhythm", {}),
                emotion_signature=fingerprint_data.get("emotion_signature", {}),
                interaction_style=fingerprint_data.get("interaction_style", {}),
                statistical_signatures=fingerprint_data.get(
                    "statistical_signatures", {}
                ),
                temporal_patterns=fingerprint_data.get("temporal_patterns", {}),
                confidence_score=fingerprint_data.get("confidence_score", 0.0),
            )

            logger.info(f"✅ Created behavioral fingerprint for speaker {speaker_id}")
            return fingerprint

        except Exception as e:
            logger.error(
                f"❌ Failed to create behavioral fingerprint for speaker {speaker_id}: {e}"
            )
            raise

    def identify_speaker_by_behavior(
        self, segments_data: List[Dict[str, Any]], threshold: float = 0.7
    ) -> Optional[Tuple[Any, float]]:
        """
        Identify speaker by behavioral patterns.

        Args:
            segments_data: List of speaker segments with text and metadata
            threshold: Similarity threshold for identification

        Returns:
            Tuple of (speaker, confidence_score) or None if no match
        """
        try:
            logger.info("🔧 Attempting speaker identification by behavior")

            # Create fingerprint for current data
            current_fingerprint = self._create_comprehensive_fingerprint(
                segments_data,
                " ".join(segment.get("text", "") for segment in segments_data),
            )

            # Get all speakers with fingerprints
            speakers = self.speaker_repo.find_speakers(active_only=True)

            best_match = None
            best_score = 0.0

            for speaker in speakers:
                fingerprint = self.profile_repo.get_current_fingerprint(speaker.id)
                if not fingerprint:
                    continue

                # Calculate similarity
                similarity = self._calculate_fingerprint_similarity(
                    current_fingerprint, fingerprint.fingerprint_data
                )

                if similarity > best_score and similarity >= threshold:
                    best_match = speaker
                    best_score = similarity

            if best_match:
                logger.info(
                    f"✅ Identified speaker: {best_match.name} (confidence: {best_score:.3f})"
                )
                return best_match, best_score
            else:
                logger.info("❌ No speaker identified by behavioral patterns")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to identify speaker by behavior: {e}")
            return None

    def _analyze_behavioral_patterns(
        self, segments_data: List[Dict[str, Any]], combined_text: str
    ) -> Dict[str, Any]:
        """
        Analyze behavioral patterns from speaker data.

        Args:
            segments_data: List of speaker segments
            combined_text: Combined text from all segments

        Returns:
            Dictionary of behavioral analysis results
        """
        try:
            # Extract text and timing data
            texts = [segment.get("text", "") for segment in segments_data]
            timings = [segment.get("start", 0) for segment in segments_data]

            # Vocabulary analysis
            vocabulary_patterns = self._analyze_vocabulary_patterns(texts)

            # Speech pattern analysis
            speech_patterns = self._analyze_speech_patterns(segments_data)

            # Emotion analysis
            emotion_patterns = self._analyze_emotion_patterns(texts)

            # Sentiment analysis
            sentiment_patterns = self._analyze_sentiment_patterns(texts)

            # Verbal tics analysis
            tics_patterns = self._analyze_verbal_tics(combined_text)

            # Named entity analysis
            entity_patterns = self._analyze_entity_patterns(combined_text)

            return {
                "vocabulary_patterns": vocabulary_patterns,
                "speech_patterns": speech_patterns,
                "emotion_patterns": emotion_patterns,
                "sentiment_patterns": sentiment_patterns,
                "tics_patterns": tics_patterns,
                "entity_patterns": entity_patterns,
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze behavioral patterns: {e}")
            return {}

    def _analyze_vocabulary_patterns(self, texts: List[str]) -> Dict[str, Any]:
        """Analyze vocabulary patterns using TF-IDF."""
        try:
            if not texts:
                return {}

            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(
                max_features=100, stop_words="english", ngram_range=(1, 2)
            )

            # Fit and transform
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()

            # Get top features for each text
            top_features = []
            for i in range(len(texts)):
                doc_features = tfidf_matrix[i].toarray()[0]
                top_indices = np.argsort(doc_features)[-10:]  # Top 10 features
                top_features.extend([feature_names[idx] for idx in top_indices])

            # Count feature frequencies
            feature_counts = {}
            for feature in top_features:
                feature_counts[feature] = feature_counts.get(feature, 0) + 1

            return {
                "top_features": dict(
                    sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)[
                        :20
                    ]
                ),
                "vocabulary_richness": len(set(" ".join(texts).split()))
                / max(len(" ".join(texts).split()), 1),
                "average_word_length": np.mean(
                    [len(word) for text in texts for word in text.split()]
                ),
                "unique_words_ratio": len(set(" ".join(texts).split()))
                / max(len(" ".join(texts).split()), 1),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze vocabulary patterns: {e}")
            return {}

    def _analyze_speech_patterns(
        self, segments_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze speech patterns and timing."""
        try:
            if not segments_data:
                return {}

            # Extract timing data
            durations = []
            word_counts = []
            speaking_rates = []

            for segment in segments_data:
                start = segment.get("start", 0)
                end = segment.get("end", start)
                duration = end - start
                text = segment.get("text", "")
                word_count = len(text.split())

                if duration > 0:
                    durations.append(duration)
                    word_counts.append(word_count)
                    speaking_rates.append(word_count / duration)

            return {
                "average_segment_duration": np.mean(durations) if durations else 0,
                "average_words_per_segment": np.mean(word_counts) if word_counts else 0,
                "average_speaking_rate": (
                    np.mean(speaking_rates) if speaking_rates else 0
                ),
                "speaking_rate_variance": (
                    np.var(speaking_rates) if speaking_rates else 0
                ),
                "total_speaking_time": sum(durations),
                "segment_count": len(segments_data),
                "longest_segment": max(durations) if durations else 0,
                "shortest_segment": min(durations) if durations else 0,
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze speech patterns: {e}")
            return {}

    def _analyze_emotion_patterns(self, texts: List[str]) -> Dict[str, Any]:
        """Analyze emotion patterns in text."""
        try:
            if not texts:
                return {}

            emotion_scores = []
            dominant_emotions = []

            for text in texts:
                if text.strip():
                    emotions = compute_nrc_emotions(text)
                    emotion_scores.append(emotions)

                    # Find dominant emotion
                    if emotions:
                        dominant_emotion = max(emotions.items(), key=lambda x: x[1])[0]
                        dominant_emotions.append(dominant_emotion)

            if not emotion_scores:
                return {}

            # Calculate average emotion scores
            avg_emotions = {}
            for emotion in emotion_scores[0].keys():
                avg_emotions[emotion] = np.mean(
                    [score.get(emotion, 0) for score in emotion_scores]
                )

            # Count dominant emotions
            emotion_counts = {}
            for emotion in dominant_emotions:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

            return {
                "average_emotion_scores": avg_emotions,
                "dominant_emotion_counts": emotion_counts,
                "most_dominant_emotion": (
                    max(emotion_counts.items(), key=lambda x: x[1])[0]
                    if emotion_counts
                    else None
                ),
                "emotion_variance": (
                    np.var(list(avg_emotions.values())) if avg_emotions else 0
                ),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze emotion patterns: {e}")
            return {}

    def _analyze_sentiment_patterns(self, texts: List[str]) -> Dict[str, Any]:
        """Analyze sentiment patterns in text."""
        try:
            if not texts:
                return {}

            sentiment_scores = []

            for text in texts:
                if text.strip():
                    sentiment = score_sentiment(text)
                    # Extract compound score from dict (VADER returns dict with 'compound', 'pos', 'neg', 'neu')
                    compound_score = sentiment.get("compound", 0.0)
                    sentiment_scores.append(compound_score)

            if not sentiment_scores:
                return {}

            return {
                "average_sentiment": np.mean(sentiment_scores),
                "sentiment_variance": np.var(sentiment_scores),
                "positive_segments": sum(1 for score in sentiment_scores if score > 0),
                "negative_segments": sum(1 for score in sentiment_scores if score < 0),
                "neutral_segments": sum(1 for score in sentiment_scores if score == 0),
                "sentiment_range": (min(sentiment_scores), max(sentiment_scores)),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze sentiment patterns: {e}")
            return {}

    def _analyze_verbal_tics(self, text: str) -> Dict[str, Any]:
        """Analyze verbal tics and filler words."""
        try:
            if not text.strip():
                return {}

            tics_list = extract_tics_from_text(text)
            # Convert list to dict with counts
            tics = {}
            for tic in tics_list:
                tics[tic] = tics.get(tic, 0) + 1

            return {
                "tics_found": list(tics.keys()),
                "tics_frequency": tics,
                "total_tics": sum(tics.values()),
                "tics_density": sum(tics.values()) / max(len(text.split()), 1),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze verbal tics: {e}")
            return {}

    def _analyze_entity_patterns(self, text: str) -> Dict[str, Any]:
        """Analyze named entity patterns."""
        try:
            if not text.strip():
                return {}

            entities = extract_named_entities(text)
            # Convert tuples (text, label_) to dicts
            entity_dicts = [{"text": text, "type": label} for text, label in entities]

            # Group entities by type
            entity_types = {}
            for entity in entity_dicts:
                entity_type = entity.get("type", "UNKNOWN")
                entity_text = entity.get("text", "")

                if entity_type not in entity_types:
                    entity_types[entity_type] = []
                entity_types[entity_type].append(entity_text)

            return {
                "entity_types": entity_types,
                "total_entities": len(entity_dicts),
                "unique_entities": len(
                    set(entity.get("text", "") for entity in entity_dicts)
                ),
                "most_common_entity_type": (
                    max(entity_types.items(), key=lambda x: len(x[1]))[0]
                    if entity_types
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"❌ Failed to analyze entity patterns: {e}")
            return {}

    def _create_comprehensive_fingerprint(
        self, segments_data: List[Dict[str, Any]], combined_text: str
    ) -> Dict[str, Any]:
        """Create a comprehensive behavioral fingerprint."""
        try:
            behavioral_data = self._analyze_behavioral_patterns(
                segments_data, combined_text
            )

            # Calculate confidence score based on data quality
            confidence_score = self._calculate_confidence_score(
                segments_data, behavioral_data
            )

            return {
                "behavioral_data": behavioral_data,
                "confidence_score": confidence_score,
                "fingerprint_timestamp": datetime.utcnow().isoformat(),
                "data_quality_metrics": {
                    "segment_count": len(segments_data),
                    "total_words": len(combined_text.split()),
                    "average_segment_length": (
                        np.mean(
                            [
                                len(segment.get("text", "").split())
                                for segment in segments_data
                            ]
                        )
                        if segments_data
                        else 0
                    ),
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to create comprehensive fingerprint: {e}")
            return {}

    def _calculate_confidence_score(
        self, segments_data: List[Dict[str, Any]], behavioral_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for behavioral fingerprint."""
        try:
            score = 0.0

            # Base score from data quality
            if len(segments_data) >= 10:
                score += 0.3
            elif len(segments_data) >= 5:
                score += 0.2
            elif len(segments_data) >= 2:
                score += 0.1

            # Score from behavioral analysis completeness
            analysis_components = [
                "vocabulary_patterns",
                "speech_patterns",
                "emotion_patterns",
                "sentiment_patterns",
                "tics_patterns",
                "entity_patterns",
            ]

            for component in analysis_components:
                if behavioral_data.get(component):
                    score += 0.1

            # Normalize to 0-1 range
            return min(score, 1.0)

        except Exception as e:
            logger.error(f"❌ Failed to calculate confidence score: {e}")
            return 0.0

    def _calculate_fingerprint_similarity(
        self, fingerprint1: Dict[str, Any], fingerprint2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two behavioral fingerprints."""
        try:
            # Extract behavioral data
            data1 = fingerprint1.get("behavioral_data", {})
            data2 = fingerprint2.get("behavioral_data", {})

            similarities = []

            # Compare vocabulary patterns
            vocab1 = data1.get("vocabulary_patterns", {}).get("top_features", {})
            vocab2 = data2.get("vocabulary_patterns", {}).get("top_features", {})
            if vocab1 and vocab2:
                vocab_similarity = self._calculate_dict_similarity(vocab1, vocab2)
                similarities.append(vocab_similarity * 0.3)  # Weight: 30%

            # Compare emotion patterns
            emotion1 = data1.get("emotion_patterns", {}).get(
                "average_emotion_scores", {}
            )
            emotion2 = data2.get("emotion_patterns", {}).get(
                "average_emotion_scores", {}
            )
            if emotion1 and emotion2:
                emotion_similarity = self._calculate_dict_similarity(emotion1, emotion2)
                similarities.append(emotion_similarity * 0.25)  # Weight: 25%

            # Compare speech patterns
            speech1 = data1.get("speech_patterns", {})
            speech2 = data2.get("speech_patterns", {})
            if speech1 and speech2:
                speech_similarity = self._calculate_speech_similarity(speech1, speech2)
                similarities.append(speech_similarity * 0.25)  # Weight: 25%

            # Compare sentiment patterns
            sentiment1 = data1.get("sentiment_patterns", {})
            sentiment2 = data2.get("sentiment_patterns", {})
            if sentiment1 and sentiment2:
                sentiment_similarity = self._calculate_sentiment_similarity(
                    sentiment1, sentiment2
                )
                similarities.append(sentiment_similarity * 0.2)  # Weight: 20%

            return np.mean(similarities) if similarities else 0.0

        except Exception as e:
            logger.error(f"❌ Failed to calculate fingerprint similarity: {e}")
            return 0.0

    def _calculate_dict_similarity(
        self, dict1: Dict[str, Any], dict2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two dictionaries."""
        try:
            all_keys = set(dict1.keys()) | set(dict2.keys())
            if not all_keys:
                return 0.0

            similarities = []
            for key in all_keys:
                val1 = dict1.get(key, 0)
                val2 = dict2.get(key, 0)

                if val1 == 0 and val2 == 0:
                    similarities.append(1.0)  # Both zero = similar
                elif val1 == 0 or val2 == 0:
                    similarities.append(0.0)  # One zero, one non-zero = different
                else:
                    # Calculate relative similarity
                    max_val = max(val1, val2)
                    similarity = min(val1, val2) / max_val
                    similarities.append(similarity)

            return np.mean(similarities)

        except Exception as e:
            logger.error(f"❌ Failed to calculate dict similarity: {e}")
            return 0.0

    def _calculate_speech_similarity(
        self, speech1: Dict[str, Any], speech2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between speech patterns."""
        try:
            similarities = []

            # Compare speaking rates
            rate1 = speech1.get("average_speaking_rate", 0)
            rate2 = speech2.get("average_speaking_rate", 0)
            if rate1 > 0 and rate2 > 0:
                rate_similarity = min(rate1, rate2) / max(rate1, rate2)
                similarities.append(rate_similarity)

            # Compare segment durations
            duration1 = speech1.get("average_segment_duration", 0)
            duration2 = speech2.get("average_segment_duration", 0)
            if duration1 > 0 and duration2 > 0:
                duration_similarity = min(duration1, duration2) / max(
                    duration1, duration2
                )
                similarities.append(duration_similarity)

            return np.mean(similarities) if similarities else 0.0

        except Exception as e:
            logger.error(f"❌ Failed to calculate speech similarity: {e}")
            return 0.0

    def _calculate_sentiment_similarity(
        self, sentiment1: Dict[str, Any], sentiment2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between sentiment patterns."""
        try:
            avg1 = sentiment1.get("average_sentiment", 0)
            avg2 = sentiment2.get("average_sentiment", 0)

            # Normalize to 0-1 range and calculate similarity
            normalized1 = (avg1 + 1) / 2  # Convert from [-1, 1] to [0, 1]
            normalized2 = (avg2 + 1) / 2

            return 1 - abs(normalized1 - normalized2)

        except Exception as e:
            logger.error(f"❌ Failed to calculate sentiment similarity: {e}")
            return 0.0

    def _merge_behavioral_data(
        self, existing_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> None:
        """Merge new behavioral data into existing data."""
        try:
            for key, new_value in new_data.items():
                if key not in existing_data:
                    existing_data[key] = new_value
                elif isinstance(new_value, dict) and isinstance(
                    existing_data[key], dict
                ):
                    self._merge_behavioral_data(existing_data[key], new_value)
                elif isinstance(new_value, (int, float)) and isinstance(
                    existing_data[key], (int, float)
                ):
                    # Average numeric values
                    existing_data[key] = (existing_data[key] + new_value) / 2

        except Exception as e:
            logger.error(f"❌ Failed to merge behavioral data: {e}")

    def _generate_preferences(self, behavioral_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate speaker preferences based on behavioral data."""
        try:
            preferences = {
                "analysis_focus": [],
                "visualization_preferences": {},
                "notification_settings": {},
                "created_at": datetime.utcnow().isoformat(),
            }

            # Determine analysis focus based on behavioral patterns
            if (
                behavioral_data.get("emotion_patterns", {}).get("emotion_variance", 0)
                > 0.5
            ):
                preferences["analysis_focus"].append("emotion_analysis")

            if (
                behavioral_data.get("sentiment_patterns", {}).get(
                    "sentiment_variance", 0
                )
                > 0.3
            ):
                preferences["analysis_focus"].append("sentiment_tracking")

            if behavioral_data.get("tics_patterns", {}).get("total_tics", 0) > 5:
                preferences["analysis_focus"].append("speech_patterns")

            return preferences

        except Exception as e:
            logger.error(f"❌ Failed to generate preferences: {e}")
            return {}

    def _generate_settings(self, behavioral_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate analysis settings based on behavioral data."""
        try:
            settings = {
                "analysis_depth": "standard",
                "performance_optimization": "balanced",
                "caching_enabled": True,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Adjust settings based on behavioral complexity
            total_patterns = sum(1 for pattern in behavioral_data.values() if pattern)

            if total_patterns >= 5:
                settings["analysis_depth"] = "comprehensive"
            elif total_patterns >= 3:
                settings["analysis_depth"] = "standard"
            else:
                settings["analysis_depth"] = "basic"

            return settings

        except Exception as e:
            logger.error(f"❌ Failed to generate settings: {e}")
            return {}

    def close(self) -> None:
        """Close the service and cleanup resources."""
        if self.session:
            self.session.close()
        logger.info("🔧 Speaker profiling service closed")


class SpeakerIdentityService:
    """
    Service for canonical speaker identity resolution.

    **CRITICAL INVARIANT**: No analysis module may create, modify, or infer speaker identity.
    All speaker identity decisions must pass through SpeakerIdentityService and be logged
    as resolution events in the speaker_resolution_events table.

    This ensures:
    - Single source of truth for speaker identity
    - Complete audit trail of all identity decisions
    - Reproducibility of speaker resolution
    - Safe re-resolution without data corruption
    """

    def __init__(self):
        """Initialize the speaker identity service."""
        self.session = get_session()
        self.speaker_repo = SpeakerRepository(self.session)
        self.profiling_service = SpeakerProfilingService()

        # Import here to avoid circular dependency
        from transcriptx.database.vocabulary_storage import VocabularyStorageService
        from transcriptx.database.cross_session_tracking import (
            CrossSessionTrackingService,
        )

        self.vocabulary_service = VocabularyStorageService()
        self.cross_session_service = CrossSessionTrackingService()

        logger.info("🔧 Initialized speaker identity service")

    def resolve_speaker_identity(
        self,
        diarized_label: str,
        transcript_file_id: int,
        session_data: List[Dict[str, Any]],
        confidence_threshold: float = 0.7,
        analysis_run_id: Optional[str] = None,
    ) -> Tuple[Any, bool, Dict[str, Any]]:
        """
        Resolve diarized label to canonical speaker_id.

        Process:
        1. Check for existing canonical_id match
        2. Use vocabulary matching if available
        3. Use behavioral fingerprint matching
        4. Create new speaker if no match found
        5. Log resolution decision with metadata

        Args:
            diarized_label: Diarized speaker label (e.g., "SPEAKER_01", "Glen")
            transcript_file_id: ID of the transcript file
            session_data: List of segment dictionaries for this speaker
            confidence_threshold: Minimum confidence for matching
            analysis_run_id: Optional UUID linking resolution to analysis run

        Returns:
            Tuple of (speaker, is_new, resolution_metadata)

        resolution_metadata format:
        {
            "method": "vocabulary_match" | "canonical_id" | "behavioral_fingerprint" | "new_speaker",
            "confidence": 0.82,
            "evidence": {
                "top_terms": ["basically", "net-zero", "sort of"],  # if vocabulary_match
                "canonical_id": "...",  # if canonical_id match
                "fingerprint_similarity": 0.75  # if behavioral_fingerprint
            },
            "timestamp": "2024-01-01T12:00:00Z"
        }

        This metadata is stored in SpeakerResolutionEvent table for explainability.
        Confidence scores must be comparable across methods (0.0-1.0 scale).
        Every resolution decision is logged as a schema-backed event.
        """
        from datetime import datetime
        from transcriptx.database.models import SpeakerResolutionEvent

        try:
            logger.info(
                f"🔧 Resolving speaker identity for diarized label: {diarized_label}"
            )

            resolution_metadata = {
                "method": None,
                "confidence": 0.0,
                "evidence": {},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            speaker = None
            is_new = False

            # Step 1: Check for existing canonical_id match
            # If diarized_label looks like a name (not SPEAKER_XX), check canonical_id
            if diarized_label and not diarized_label.startswith("SPEAKER_"):
                canonical_id = diarized_label.lower().strip()
                existing_speaker = self.speaker_repo.get_speaker_by_canonical_id(
                    canonical_id
                )

                if existing_speaker:
                    speaker = existing_speaker
                    is_new = False
                    resolution_metadata["method"] = "canonical_id"
                    resolution_metadata["confidence"] = 1.0
                    resolution_metadata["evidence"]["canonical_id"] = canonical_id
                    logger.info(
                        f"✅ Matched via canonical_id: {canonical_id} -> {speaker.name}"
                    )

            # Step 2: Use vocabulary matching if no canonical match
            if not speaker and session_data:
                # Extract text from session data
                texts = [seg.get("text", "") for seg in session_data if seg.get("text")]
                combined_text = " ".join(texts)

                if combined_text.strip():
                    vocabulary_matches = (
                        self.vocabulary_service.find_speakers_by_vocabulary(
                            text=combined_text,
                            top_n=1,
                            min_confidence=confidence_threshold,
                            transcript_file_id=transcript_file_id,
                        )
                    )

                    if vocabulary_matches:
                        matched_speaker, confidence = vocabulary_matches[0]
                        if confidence >= confidence_threshold:
                            speaker = matched_speaker
                            is_new = False
                            resolution_metadata["method"] = "vocabulary_match"
                            resolution_metadata["confidence"] = confidence

                            # Extract top terms from vocabulary (simplified)
                            # In production, you'd get this from the vocabulary service
                            resolution_metadata["evidence"]["top_terms"] = []
                            logger.info(
                                f"✅ Matched via vocabulary: {diarized_label} -> {speaker.name} (confidence: {confidence:.2f})"
                            )

            # Step 3: Use behavioral fingerprint matching
            if not speaker and session_data:
                try:
                    fingerprint_matches = (
                        self.cross_session_service.find_speaker_matches(
                            speaker_name=diarized_label,
                            session_data=session_data,
                            confidence_threshold=confidence_threshold,
                        )
                    )

                    if fingerprint_matches:
                        matched_speaker, confidence = fingerprint_matches[0]
                        if confidence >= confidence_threshold:
                            speaker = matched_speaker
                            is_new = False
                            resolution_metadata["method"] = "behavioral_fingerprint"
                            resolution_metadata["confidence"] = confidence
                            resolution_metadata["evidence"][
                                "fingerprint_similarity"
                            ] = confidence
                            logger.info(
                                f"✅ Matched via behavioral fingerprint: {diarized_label} -> {speaker.name} (confidence: {confidence:.2f})"
                            )
                except Exception as e:
                    logger.debug(f"Behavioral fingerprint matching failed: {e}")

            # Step 4: Create new speaker if no match found
            if not speaker:
                speaker, is_new = self.profiling_service.create_or_get_speaker(
                    name=diarized_label, display_name=diarized_label
                )

                # Set canonical_id if it's a real name
                if (
                    is_new
                    and diarized_label
                    and not diarized_label.startswith("SPEAKER_")
                ):
                    speaker.canonical_id = diarized_label.lower().strip()
                    speaker.confidence_score = 1.0
                    self.session.commit()

                resolution_metadata["method"] = "new_speaker"
                resolution_metadata["confidence"] = 1.0 if is_new else 0.5
                logger.info(
                    f"✅ Created new speaker: {diarized_label} (ID: {speaker.id})"
                )

            # Step 5: Log resolution event
            resolution_event = SpeakerResolutionEvent(
                transcript_file_id=transcript_file_id,
                speaker_id=speaker.id if speaker else None,
                diarized_label=diarized_label,
                method=resolution_metadata["method"],
                confidence=resolution_metadata["confidence"],
                evidence_json=resolution_metadata["evidence"],
                analysis_run_id=analysis_run_id,
            )

            self.session.add(resolution_event)
            self.session.commit()

            logger.info(
                f"✅ Logged resolution event: {diarized_label} -> {speaker.name if speaker else 'UNRESOLVED'} ({resolution_metadata['method']})"
            )

            return speaker, is_new, resolution_metadata

        except Exception as e:
            logger.error(
                f"❌ Failed to resolve speaker identity for {diarized_label}: {e}"
            )
            if self.session:
                self.session.rollback()
            raise

    def update_speaker_canonical_id(
        self, speaker_id: int, canonical_id: str, confidence_score: float
    ) -> None:
        """
        Update canonical_id with explicit logging.

        Args:
            speaker_id: Speaker ID
            canonical_id: New canonical ID
            confidence_score: Confidence in the canonical ID
        """
        try:
            speaker = self.speaker_repo.get_speaker_by_id(speaker_id)
            if speaker:
                speaker.canonical_id = canonical_id
                speaker.confidence_score = confidence_score
                self.session.commit()
                logger.info(
                    f"✅ Updated canonical_id for speaker {speaker_id}: {canonical_id}"
                )
            else:
                logger.warning(f"⚠️ Speaker {speaker_id} not found")
        except Exception as e:
            logger.error(f"❌ Failed to update canonical_id: {e}")
            if self.session:
                self.session.rollback()
            raise

    def close(self) -> None:
        """Close the service and cleanup resources."""
        if self.session:
            self.session.close()
        if self.vocabulary_service:
            self.vocabulary_service.close()
        logger.info("🔧 Speaker identity service closed")
