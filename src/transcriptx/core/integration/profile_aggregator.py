"""
Speaker profile aggregator for TranscriptX.

This module provides the SpeakerProfileAggregator class that aggregates data
from all analysis types into comprehensive speaker profiles.
"""

import logging
from typing import Any, Dict, List, Optional

from transcriptx.database.models import (
    Speaker,
    SpeakerSentimentProfile,
    SpeakerEmotionProfile,
    SpeakerTopicProfile,
    SpeakerEntityProfile,
    SpeakerTicProfile,
    SpeakerSemanticProfile,
    SpeakerInteractionProfile,
    SpeakerPerformanceProfile,
)

logger = logging.getLogger(__name__)


class SpeakerProfileAggregator:
    """
    Speaker profile aggregator for TranscriptX.

    This class aggregates data from all analysis types into comprehensive
    speaker profiles, providing insights across multiple dimensions.
    """

    def __init__(self, database_session=None):
        """
        Initialize the profile aggregator.

        Args:
            database_session: SQLAlchemy database session
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.session = database_session

        # Profile types and their corresponding models
        self.profile_types = {
            "sentiment": SpeakerSentimentProfile,
            "emotion": SpeakerEmotionProfile,
            "topic": SpeakerTopicProfile,
            "entity": SpeakerEntityProfile,
            "tic": SpeakerTicProfile,
            "semantic": SpeakerSemanticProfile,
            "interaction": SpeakerInteractionProfile,
            "performance": SpeakerPerformanceProfile,
        }

    def aggregate_profiles(self, conversation_id: int) -> Dict[str, Any]:
        """
        Aggregate speaker profiles for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            Dictionary containing aggregation results
        """
        self.logger.info(f"Aggregating profiles for conversation {conversation_id}")

        try:
            # Get speakers for the conversation
            speakers = self._get_conversation_speakers(conversation_id)

            aggregation_results = {
                "conversation_id": conversation_id,
                "speakers_aggregated": 0,
                "errors": [],
                "speaker_results": {},
            }

            for speaker in speakers:
                try:
                    speaker_result = self.aggregate_speaker_profile(speaker.id)
                    aggregation_results["speaker_results"][speaker.id] = speaker_result
                    aggregation_results["speakers_aggregated"] += 1

                except Exception as e:
                    error_msg = f"Failed to aggregate profile for speaker {speaker.id}: {str(e)}"
                    self.logger.error(error_msg)
                    aggregation_results["errors"].append(error_msg)

            self.logger.info(
                f"Profile aggregation complete: {aggregation_results['speakers_aggregated']} "
                f"speakers aggregated"
            )

            return aggregation_results

        except Exception as e:
            self.logger.error(f"Error aggregating profiles: {str(e)}")
            raise

    def aggregate_speaker_profile(self, speaker_id: int) -> Dict[str, Any]:
        """
        Aggregate profile for a single speaker.

        Args:
            speaker_id: ID of the speaker

        Returns:
            Dictionary containing aggregated profile data
        """
        self.logger.debug(f"Aggregating profile for speaker {speaker_id}")

        aggregated_profile = {
            "speaker_id": speaker_id,
            "profile_summary": {},
            "cross_analysis_insights": {},
            "confidence_scores": {},
            "recommendations": [],
        }

        profiles = self._get_speaker_profiles(speaker_id)
        for profile_type, profile_data in profiles.items():
            if not profile_data:
                continue
            aggregated_profile["profile_summary"][profile_type] = profile_data
            aggregated_profile["confidence_scores"][profile_type] = self._calculate_confidence(
                profile_type, profile_data
            )

        # Generate cross-analysis insights
        aggregated_profile["cross_analysis_insights"] = (
            self._generate_cross_analysis_insights(
                aggregated_profile["profile_summary"]
            )
        )

        # Generate recommendations
        aggregated_profile["recommendations"] = self._generate_recommendations(
            aggregated_profile["profile_summary"]
        )

        return aggregated_profile

    def _get_conversation_speakers(self, conversation_id: int) -> List[Speaker]:
        """
        Get speakers for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of speakers
        """
        if not self.session:
            self.logger.warning("No database session available")
            return []

        try:
            # This would need to be implemented based on your database schema
            # For now, return empty list
            return []
        except Exception as e:
            self.logger.error(f"Error getting conversation speakers: {str(e)}")
            return []

    def _get_profile_data(
        self, speaker_id: int, model_class
    ) -> Optional[Dict[str, Any]]:
        """
        Get profile data for a speaker and profile type.

        Args:
            speaker_id: ID of the speaker
            model_class: Profile model class

        Returns:
            Profile data dictionary or None if not found
        """
        if not self.session:
            return None

        try:
            profile = (
                self.session.query(model_class)
                .filter(model_class.speaker_id == speaker_id)
                .first()
            )

            if profile:
                return self._serialize_profile(profile)

            return None

        except Exception as e:
            self.logger.error(f"Error getting profile data: {str(e)}")
            return None

    def _get_speaker_profiles(self, speaker_id: int) -> Dict[str, Any]:
        """Return per-type profile data for a speaker."""
        profiles: Dict[str, Any] = {}
        for profile_type, model_class in self.profile_types.items():
            try:
                profiles[profile_type] = self._get_profile_data(speaker_id, model_class)
            except Exception as e:
                self.logger.warning(
                    f"Failed to aggregate {profile_type} profile for speaker {speaker_id}: {str(e)}"
                )
        return profiles

    def _serialize_profile(self, profile) -> Dict[str, Any]:
        """
        Serialize profile object to dictionary.

        Args:
            profile: Profile object

        Returns:
            Serialized profile data
        """
        profile_data = {}

        for column in profile.__table__.columns:
            value = getattr(profile, column.name)
            profile_data[column.name] = value

        return profile_data

    def _calculate_confidence(
        self, profile_type: str, profile_data: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for a profile type.

        Args:
            profile_type: Type of profile
            profile_data: Profile data

        Returns:
            Confidence score between 0 and 1
        """
        if not profile_data:
            return 0.0

        # Calculate confidence based on data completeness and quality
        confidence_factors = {
            "sentiment": ["average_sentiment_score", "sentiment_volatility"],
            "emotion": ["dominant_emotion", "emotional_stability"],
            "topic": ["preferred_topics", "topic_engagement_style"],
            "entity": ["frequently_mentioned_entities"],
            "tic": ["tic_frequency"],
            "semantic": ["vocabulary_sophistication", "semantic_consistency"],
            "interaction": ["interaction_style", "influence_score"],
            "performance": ["speaking_style", "performance_metrics"],
        }

        factors = confidence_factors.get(profile_type, [])
        if not factors:
            return 0.5

        # Count non-null factors
        valid_factors = 0
        for factor in factors:
            if profile_data.get(factor) is not None:
                valid_factors += 1

        return valid_factors / len(factors)

    def _generate_cross_analysis_insights(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate insights across different analysis types.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Dictionary containing cross-analysis insights
        """
        insights = {
            "communication_style": self._analyze_communication_style(profile_summary),
            "emotional_intelligence": self._analyze_emotional_intelligence(
                profile_summary
            ),
            "expertise_areas": self._analyze_expertise_areas(profile_summary),
            "interaction_patterns": self._analyze_interaction_patterns(profile_summary),
            "development_areas": self._analyze_development_areas(profile_summary),
        }

        return insights

    def _analyze_communication_style(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze communication style across different dimensions.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Communication style analysis
        """
        style_analysis = {
            "overall_style": "balanced",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
        }

        # Analyze sentiment and emotion
        sentiment_data = profile_summary.get("sentiment", {})
        emotion_data = profile_summary.get("emotion", {})

        avg_sentiment = sentiment_data.get("average_sentiment_score", 0)
        emotional_stability = emotion_data.get("emotional_stability", 0.5)

        if avg_sentiment > 0.3:
            style_analysis["strengths"].append("positive communication")
        elif avg_sentiment < -0.3:
            style_analysis["weaknesses"].append("negative communication")

        if emotional_stability > 0.7:
            style_analysis["strengths"].append("emotional stability")
        elif emotional_stability < 0.3:
            style_analysis["weaknesses"].append("emotional volatility")

        return style_analysis

    def _analyze_emotional_intelligence(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze emotional intelligence indicators.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Emotional intelligence analysis
        """
        ei_analysis = {"score": 0.5, "indicators": [], "areas_for_improvement": []}

        emotion_data = profile_summary.get("emotion", {})
        interaction_data = profile_summary.get("interaction", {})

        # Calculate EI score based on various factors
        factors = []

        emotional_stability = emotion_data.get("emotional_stability", 0.5)
        factors.append(emotional_stability)

        emotion_consistency = emotion_data.get("emotion_consistency", 0.5)
        factors.append(emotion_consistency)

        collaboration_score = interaction_data.get("collaboration_score", 0.5)
        factors.append(collaboration_score)

        if factors:
            ei_analysis["score"] = sum(factors) / len(factors)

        return ei_analysis

    def _analyze_expertise_areas(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze expertise areas based on topic and entity data.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Expertise analysis
        """
        expertise_analysis = {
            "primary_areas": [],
            "secondary_areas": [],
            "expertise_level": "intermediate",
        }

        topic_data = profile_summary.get("topic", {})
        entity_data = profile_summary.get("entity", {})

        # Analyze topic expertise
        preferred_topics = topic_data.get("preferred_topics", {})
        if preferred_topics:
            sorted_topics = sorted(
                preferred_topics.items(), key=lambda x: x[1], reverse=True
            )
            expertise_analysis["primary_areas"] = [
                topic for topic, score in sorted_topics[:3]
            ]

        # Analyze entity expertise
        entity_domains = entity_data.get("entity_expertise_domains", {})
        if entity_domains:
            sorted_domains = sorted(
                entity_domains.items(), key=lambda x: x[1], reverse=True
            )
            expertise_analysis["secondary_areas"] = [
                domain for domain, score in sorted_domains[:3]
            ]

        return expertise_analysis

    def _analyze_interaction_patterns(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze interaction patterns.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Interaction pattern analysis
        """
        interaction_analysis = {
            "style": "balanced",
            "strengths": [],
            "weaknesses": [],
            "influence_level": "medium",
        }

        interaction_data = profile_summary.get("interaction", {})

        influence_score = interaction_data.get("influence_score", 0.5)
        collaboration_score = interaction_data.get("collaboration_score", 0.5)
        interaction_style = interaction_data.get("interaction_style", "balanced")

        interaction_analysis["style"] = interaction_style

        if influence_score > 0.7:
            interaction_analysis["strengths"].append("high influence")
            interaction_analysis["influence_level"] = "high"
        elif influence_score < 0.3:
            interaction_analysis["weaknesses"].append("low influence")
            interaction_analysis["influence_level"] = "low"

        if collaboration_score > 0.7:
            interaction_analysis["strengths"].append("strong collaboration")
        elif collaboration_score < 0.3:
            interaction_analysis["weaknesses"].append("limited collaboration")

        return interaction_analysis

    def _analyze_development_areas(
        self, profile_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze areas for development and improvement.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            Development areas analysis
        """
        development_analysis = {
            "priority_areas": [],
            "improvement_opportunities": [],
            "strength_areas": [],
        }

        # Analyze various dimensions for development opportunities
        for profile_type, data in profile_summary.items():
            if profile_type == "sentiment":
                avg_sentiment = data.get("average_sentiment_score", 0)
                if avg_sentiment < -0.2:
                    development_analysis["priority_areas"].append(
                        "improve positive communication"
                    )

            elif profile_type == "emotion":
                emotional_stability = data.get("emotional_stability", 0.5)
                if emotional_stability < 0.4:
                    development_analysis["priority_areas"].append(
                        "enhance emotional stability"
                    )

            elif profile_type == "interaction":
                collaboration_score = data.get("collaboration_score", 0.5)
                if collaboration_score < 0.4:
                    development_analysis["priority_areas"].append(
                        "improve collaboration skills"
                    )

        return development_analysis

    def _generate_recommendations(self, profile_summary: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on profile analysis.

        Args:
            profile_summary: Summary of all profile types

        Returns:
            List of recommendations
        """
        recommendations = []

        # Generate recommendations based on cross-analysis insights
        insights = self._generate_cross_analysis_insights(profile_summary)

        # Communication style recommendations
        communication_style = insights.get("communication_style", {})
        if "negative communication" in communication_style.get("weaknesses", []):
            recommendations.append(
                "Focus on positive language and constructive feedback"
            )

        if "emotional volatility" in communication_style.get("weaknesses", []):
            recommendations.append("Practice emotional regulation techniques")

        # Emotional intelligence recommendations
        ei_analysis = insights.get("emotional_intelligence", {})
        ei_score = ei_analysis.get("score", 0.5)
        if ei_score < 0.4:
            recommendations.append(
                "Develop emotional intelligence through self-awareness exercises"
            )

        # Interaction recommendations
        interaction_patterns = insights.get("interaction_patterns", {})
        if "low influence" in interaction_patterns.get("weaknesses", []):
            recommendations.append(
                "Build influence through active listening and clear communication"
            )

        if "limited collaboration" in interaction_patterns.get("weaknesses", []):
            recommendations.append(
                "Enhance collaboration skills through team-building activities"
            )

        return recommendations
