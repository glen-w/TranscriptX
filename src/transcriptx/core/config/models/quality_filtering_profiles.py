"""Pydantic schema for analysis.quality_filtering_profiles."""

from pydantic import BaseModel, Field


class QualityFilteringProfilesSettingsModelBalancedModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=3.0)
    length_good: float = Field(default=1.0)
    complex_reasoning: float = Field(default=2.0)
    opinions_ideas: float = Field(default=2.0)
    agreement_disagreement: float = Field(default=1.0)
    filler_penalty: float = Field(default=-0.5)
    exact_repetition_penalty: float = Field(default=-5.0)
    high_overlap_penalty: float = Field(default=-3.0)


class QualityFilteringProfilesSettingsModelBalancedModelThresholdsModel(BaseModel):
    min_words: int = Field(default=3)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (5, 50))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (3, 100))
    overlap_threshold: float = Field(default=0.7)


class QualityFilteringProfilesSettingsModelBalancedModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: [
            "because",
            "however",
            "therefore",
            "although",
            "meanwhile",
        ]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: ["think", "believe", "suggest", "propose", "recommend"]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: ["agree", "disagree", "yes", "no", "correct", "wrong"]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
        ]
    )


class QualityFilteringProfilesSettingsModelBalancedModel(BaseModel):
    description: str = Field(default="Balanced approach for general conversations")
    weights: QualityFilteringProfilesSettingsModelBalancedModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelBalancedModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelBalancedModelThresholdsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelBalancedModelThresholdsModel
        )
    )
    indicators: QualityFilteringProfilesSettingsModelBalancedModelIndicatorsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelBalancedModelIndicatorsModel
        )
    )


class QualityFilteringProfilesSettingsModelAcademicModelWeightsModelDialogueActsModel(
    BaseModel
):
    question: float = Field(default=4.0)
    suggestion: float = Field(default=3.0)
    agreement: float = Field(default=2.5)
    disagreement: float = Field(default=3.0)
    statement: float = Field(default=2.0)
    acknowledgement: float = Field(default=0.5)
    hesitation: float = Field(default=-1.5)


class QualityFilteringProfilesSettingsModelAcademicModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=4.0)
    length_good: float = Field(default=1.5)
    complex_reasoning: float = Field(default=4.0)
    opinions_ideas: float = Field(default=3.0)
    agreement_disagreement: float = Field(default=2.0)
    filler_penalty: float = Field(default=-1.0)
    exact_repetition_penalty: float = Field(default=-3.0)
    high_overlap_penalty: float = Field(default=-2.0)
    dialogue_acts: (
        QualityFilteringProfilesSettingsModelAcademicModelWeightsModelDialogueActsModel
    ) = Field(
        default_factory=QualityFilteringProfilesSettingsModelAcademicModelWeightsModelDialogueActsModel
    )
    sentiment_strength: float = Field(default=1.0)
    verbal_tic_penalty: float = Field(default=-2.5)
    optimal_readability: float = Field(default=3.0)
    topic_relevance: float = Field(default=2.5)
    entity_engagement: float = Field(default=2.0)


class QualityFilteringProfilesSettingsModelAcademicModelThresholdsModel(BaseModel):
    min_words: int = Field(default=5)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (8, 80))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (5, 150))
    overlap_threshold: float = Field(default=0.8)


class QualityFilteringProfilesSettingsModelAcademicModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: [
            "because",
            "however",
            "therefore",
            "although",
            "meanwhile",
            "consequently",
            "furthermore",
            "moreover",
            "nevertheless",
            "nonetheless",
            "thus",
            "hence",
        ]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: [
            "think",
            "believe",
            "suggest",
            "propose",
            "recommend",
            "consider",
            "hypothesize",
            "conclude",
            "argue",
            "demonstrate",
            "theorize",
            "postulate",
        ]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: [
            "agree",
            "disagree",
            "yes",
            "no",
            "correct",
            "wrong",
            "exactly",
            "absolutely",
            "precisely",
            "inaccurate",
            "valid",
            "invalid",
        ]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
            "basically",
            "actually",
        ]
    )


class QualityFilteringProfilesSettingsModelAcademicModel(BaseModel):
    description: str = Field(
        default="Optimized for academic discussions, research presentations, and debates"
    )
    weights: QualityFilteringProfilesSettingsModelAcademicModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelAcademicModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelAcademicModelThresholdsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelAcademicModelThresholdsModel
        )
    )
    indicators: QualityFilteringProfilesSettingsModelAcademicModelIndicatorsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelAcademicModelIndicatorsModel
        )
    )


class QualityFilteringProfilesSettingsModelBusinessModelWeightsModelDialogueActsModel(
    BaseModel
):
    question: float = Field(default=3.5)
    suggestion: float = Field(default=4.0)
    agreement: float = Field(default=3.0)
    disagreement: float = Field(default=2.5)
    statement: float = Field(default=2.5)
    acknowledgement: float = Field(default=1.0)
    hesitation: float = Field(default=-0.5)


class QualityFilteringProfilesSettingsModelBusinessModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=3.5)
    length_good: float = Field(default=1.0)
    complex_reasoning: float = Field(default=2.5)
    opinions_ideas: float = Field(default=4.0)
    agreement_disagreement: float = Field(default=2.5)
    filler_penalty: float = Field(default=-0.3)
    exact_repetition_penalty: float = Field(default=-4.0)
    high_overlap_penalty: float = Field(default=-2.5)
    dialogue_acts: (
        QualityFilteringProfilesSettingsModelBusinessModelWeightsModelDialogueActsModel
    ) = Field(
        default_factory=QualityFilteringProfilesSettingsModelBusinessModelWeightsModelDialogueActsModel
    )
    sentiment_strength: float = Field(default=1.5)
    verbal_tic_penalty: float = Field(default=-1.5)
    optimal_readability: float = Field(default=2.5)
    topic_relevance: float = Field(default=3.0)
    entity_engagement: float = Field(default=2.5)


class QualityFilteringProfilesSettingsModelBusinessModelThresholdsModel(BaseModel):
    min_words: int = Field(default=3)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (5, 60))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (3, 120))
    overlap_threshold: float = Field(default=0.75)


class QualityFilteringProfilesSettingsModelBusinessModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: [
            "because",
            "however",
            "therefore",
            "although",
            "meanwhile",
            "consequently",
        ]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: [
            "think",
            "believe",
            "suggest",
            "propose",
            "recommend",
            "consider",
            "feel",
            "assume",
            "recommend",
            "advise",
            "propose",
            "plan",
        ]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: [
            "agree",
            "disagree",
            "yes",
            "no",
            "correct",
            "wrong",
            "exactly",
            "absolutely",
            "sounds good",
            "i'm on board",
            "approved",
            "rejected",
        ]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
        ]
    )


class QualityFilteringProfilesSettingsModelBusinessModel(BaseModel):
    description: str = Field(
        default="Optimized for business meetings, negotiations, and professional discussions"
    )
    weights: QualityFilteringProfilesSettingsModelBusinessModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelBusinessModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelBusinessModelThresholdsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelBusinessModelThresholdsModel
        )
    )
    indicators: QualityFilteringProfilesSettingsModelBusinessModelIndicatorsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelBusinessModelIndicatorsModel
        )
    )


class QualityFilteringProfilesSettingsModelCasualModelWeightsModelDialogueActsModel(
    BaseModel
):
    question: float = Field(default=2.5)
    suggestion: float = Field(default=2.0)
    agreement: float = Field(default=2.5)
    disagreement: float = Field(default=2.0)
    statement: float = Field(default=2.0)
    acknowledgement: float = Field(default=1.5)
    hesitation: float = Field(default=-0.3)


class QualityFilteringProfilesSettingsModelCasualModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=2.5)
    length_good: float = Field(default=1.5)
    complex_reasoning: float = Field(default=1.5)
    opinions_ideas: float = Field(default=2.5)
    agreement_disagreement: float = Field(default=2.0)
    filler_penalty: float = Field(default=-0.2)
    exact_repetition_penalty: float = Field(default=-3.0)
    high_overlap_penalty: float = Field(default=-2.0)
    dialogue_acts: (
        QualityFilteringProfilesSettingsModelCasualModelWeightsModelDialogueActsModel
    ) = Field(
        default_factory=QualityFilteringProfilesSettingsModelCasualModelWeightsModelDialogueActsModel
    )
    sentiment_strength: float = Field(default=2.0)
    verbal_tic_penalty: float = Field(default=-0.5)
    optimal_readability: float = Field(default=1.5)
    topic_relevance: float = Field(default=1.0)
    entity_engagement: float = Field(default=1.5)


class QualityFilteringProfilesSettingsModelCasualModelThresholdsModel(BaseModel):
    min_words: int = Field(default=2)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (3, 40))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (2, 80))
    overlap_threshold: float = Field(default=0.6)


class QualityFilteringProfilesSettingsModelCasualModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: ["because", "but", "so", "though", "anyway"]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: ["think", "feel", "like", "guess", "suppose", "maybe"]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: ["yeah", "no", "right", "wrong", "sure", "okay", "cool"]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
            "basically",
            "actually",
            "literally",
        ]
    )


class QualityFilteringProfilesSettingsModelCasualModel(BaseModel):
    description: str = Field(
        default="Optimized for casual conversations, social discussions, and informal chats"
    )
    weights: QualityFilteringProfilesSettingsModelCasualModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelCasualModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelCasualModelThresholdsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelCasualModelThresholdsModel
    )
    indicators: QualityFilteringProfilesSettingsModelCasualModelIndicatorsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelCasualModelIndicatorsModel
    )


class QualityFilteringProfilesSettingsModelTechnicalModelWeightsModelDialogueActsModel(
    BaseModel
):
    question: float = Field(default=4.0)
    suggestion: float = Field(default=3.5)
    agreement: float = Field(default=2.5)
    disagreement: float = Field(default=3.5)
    statement: float = Field(default=2.5)
    acknowledgement: float = Field(default=1.0)
    hesitation: float = Field(default=-1.0)


class QualityFilteringProfilesSettingsModelTechnicalModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=3.0)
    length_good: float = Field(default=1.0)
    complex_reasoning: float = Field(default=3.5)
    opinions_ideas: float = Field(default=2.0)
    agreement_disagreement: float = Field(default=3.0)
    filler_penalty: float = Field(default=-0.8)
    exact_repetition_penalty: float = Field(default=-2.0)
    high_overlap_penalty: float = Field(default=-1.5)
    dialogue_acts: (
        QualityFilteringProfilesSettingsModelTechnicalModelWeightsModelDialogueActsModel
    ) = Field(
        default_factory=QualityFilteringProfilesSettingsModelTechnicalModelWeightsModelDialogueActsModel
    )
    sentiment_strength: float = Field(default=1.0)
    verbal_tic_penalty: float = Field(default=-2.0)
    optimal_readability: float = Field(default=2.0)
    topic_relevance: float = Field(default=4.0)
    entity_engagement: float = Field(default=3.0)


class QualityFilteringProfilesSettingsModelTechnicalModelThresholdsModel(BaseModel):
    min_words: int = Field(default=4)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (6, 70))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (4, 130))
    overlap_threshold: float = Field(default=0.85)


class QualityFilteringProfilesSettingsModelTechnicalModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: [
            "because",
            "however",
            "therefore",
            "although",
            "meanwhile",
            "consequently",
            "furthermore",
            "moreover",
            "nevertheless",
        ]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: [
            "think",
            "believe",
            "suggest",
            "propose",
            "recommend",
            "consider",
            "argue",
            "demonstrate",
            "prove",
        ]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: [
            "agree",
            "disagree",
            "yes",
            "no",
            "correct",
            "wrong",
            "exactly",
            "absolutely",
            "precisely",
            "inaccurate",
            "false",
        ]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
        ]
    )


class QualityFilteringProfilesSettingsModelTechnicalModel(BaseModel):
    description: str = Field(
        default="Optimized for technical discussions, code reviews, and troubleshooting sessions"
    )
    weights: QualityFilteringProfilesSettingsModelTechnicalModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelTechnicalModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelTechnicalModelThresholdsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelTechnicalModelThresholdsModel
        )
    )
    indicators: QualityFilteringProfilesSettingsModelTechnicalModelIndicatorsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelTechnicalModelIndicatorsModel
        )
    )


class QualityFilteringProfilesSettingsModelInterviewModelWeightsModelDialogueActsModel(
    BaseModel
):
    question: float = Field(default=4.5)
    suggestion: float = Field(default=2.0)
    agreement: float = Field(default=1.5)
    disagreement: float = Field(default=2.0)
    statement: float = Field(default=3.0)
    acknowledgement: float = Field(default=1.0)
    hesitation: float = Field(default=-1.0)


class QualityFilteringProfilesSettingsModelInterviewModelWeightsModel(BaseModel):
    length_optimal: float = Field(default=3.5)
    length_good: float = Field(default=1.0)
    complex_reasoning: float = Field(default=2.0)
    opinions_ideas: float = Field(default=3.5)
    agreement_disagreement: float = Field(default=1.5)
    filler_penalty: float = Field(default=-0.5)
    exact_repetition_penalty: float = Field(default=-3.5)
    high_overlap_penalty: float = Field(default=-2.5)
    dialogue_acts: (
        QualityFilteringProfilesSettingsModelInterviewModelWeightsModelDialogueActsModel
    ) = Field(
        default_factory=QualityFilteringProfilesSettingsModelInterviewModelWeightsModelDialogueActsModel
    )
    sentiment_strength: float = Field(default=1.5)
    verbal_tic_penalty: float = Field(default=-1.5)
    optimal_readability: float = Field(default=2.5)
    topic_relevance: float = Field(default=3.5)
    entity_engagement: float = Field(default=2.0)


class QualityFilteringProfilesSettingsModelInterviewModelThresholdsModel(BaseModel):
    min_words: int = Field(default=4)
    optimal_word_range: tuple[int, int] = Field(default_factory=lambda: (6, 60))
    good_word_range: tuple[int, int] = Field(default_factory=lambda: (4, 100))
    overlap_threshold: float = Field(default=0.75)


class QualityFilteringProfilesSettingsModelInterviewModelIndicatorsModel(BaseModel):
    complex_reasoning: list[str] = Field(
        default_factory=lambda: [
            "because",
            "however",
            "therefore",
            "although",
            "meanwhile",
        ]
    )
    opinions_ideas: list[str] = Field(
        default_factory=lambda: [
            "think",
            "believe",
            "suggest",
            "propose",
            "recommend",
            "consider",
            "feel",
            "experience",
            "worked",
            "developed",
        ]
    )
    agreement_disagreement: list[str] = Field(
        default_factory=lambda: [
            "agree",
            "disagree",
            "yes",
            "no",
            "correct",
            "wrong",
            "exactly",
            "absolutely",
        ]
    )
    filler_words: list[str] = Field(
        default_factory=lambda: [
            "um",
            "uh",
            "like",
            "you know",
            "i mean",
            "sort of",
            "kind of",
        ]
    )


class QualityFilteringProfilesSettingsModelInterviewModel(BaseModel):
    description: str = Field(
        default="Optimized for job interviews, Q&A sessions, and structured conversations"
    )
    weights: QualityFilteringProfilesSettingsModelInterviewModelWeightsModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelInterviewModelWeightsModel
    )
    thresholds: QualityFilteringProfilesSettingsModelInterviewModelThresholdsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelInterviewModelThresholdsModel
        )
    )
    indicators: QualityFilteringProfilesSettingsModelInterviewModelIndicatorsModel = (
        Field(
            default_factory=QualityFilteringProfilesSettingsModelInterviewModelIndicatorsModel
        )
    )


class QualityFilteringProfilesSettingsModel(BaseModel):
    balanced: QualityFilteringProfilesSettingsModelBalancedModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelBalancedModel
    )
    academic: QualityFilteringProfilesSettingsModelAcademicModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelAcademicModel
    )
    business: QualityFilteringProfilesSettingsModelBusinessModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelBusinessModel
    )
    casual: QualityFilteringProfilesSettingsModelCasualModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelCasualModel
    )
    technical: QualityFilteringProfilesSettingsModelTechnicalModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelTechnicalModel
    )
    interview: QualityFilteringProfilesSettingsModelInterviewModel = Field(
        default_factory=QualityFilteringProfilesSettingsModelInterviewModel
    )
