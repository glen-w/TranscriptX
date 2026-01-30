"""Visualization ID constants for analysis modules."""

# Sentiment
VIZ_SENTIMENT_ROLLING_SPEAKER = "sentiment.rolling_sentiment.speaker"
VIZ_SENTIMENT_MULTI_SPEAKER_GLOBAL = "sentiment.multi_speaker_sentiment.global"

# Emotion
VIZ_EMOTION_RADAR_SPEAKER = "emotion.radar.speaker"
VIZ_EMOTION_RADAR_GLOBAL = "emotion.radar.global"

# NER
VIZ_NER_ENTITY_TYPES_SPEAKER = "ner.entity_types.speaker"
VIZ_NER_ENTITY_TYPES_GLOBAL = "ner.entity_types.global"

# Temporal dynamics
VIZ_TEMPORAL_ENGAGEMENT_TIMESERIES = "temporal_dynamics.engagement_timeseries.global"
VIZ_TEMPORAL_SPEAKING_RATE_TIMESERIES = (
    "temporal_dynamics.speaking_rate_timeseries.global"
)
VIZ_TEMPORAL_SENTIMENT_TIMESERIES = "temporal_dynamics.sentiment_timeseries.global"
VIZ_TEMPORAL_PHASE_DETECTION = "temporal_dynamics.phase_detection.global"
VIZ_TEMPORAL_DASHBOARD = "temporal_dynamics.temporal_dashboard.global"
VIZ_TEMPORAL_DASHBOARD_SPEAKING_RATE = (
    "temporal_dynamics.temporal_dashboard_speaking_rate.global"
)

# QA analysis
VIZ_QA_TIMELINE = "qa_analysis.qa_timeline.global"
VIZ_QA_RESPONSE_QUALITY = "qa_analysis.response_quality.global"
VIZ_QA_QUESTION_TYPE_BREAKDOWN = "qa_analysis.question_type_breakdown.global"
VIZ_QA_RESPONSE_TIME_ANALYSIS = "qa_analysis.response_time_analysis.global"

# Tics
VIZ_TICS_SPEAKER = "tics.tics.speaker"

# Entity sentiment
VIZ_ENTITY_SENTIMENT_HEATMAP = "entity_sentiment.sentiment_heatmap.global"
VIZ_ENTITY_SENTIMENT_TYPE_ANALYSIS = "entity_sentiment.entity_type_analysis.global"
VIZ_ENTITY_SENTIMENT_MENTIONS_SPEAKER = "entity_sentiment.entity_mentions.speaker"

# Contagion
VIZ_CONTAGION_MATRIX = "contagion.contagion_matrix.global"

# Dynamics
VIZ_ECHOES_HEATMAP = "echoes.echo_heatmap.global"
VIZ_ECHOES_TIMELINE = "echoes.echo_timeline.global"
VIZ_PAUSES_HIST = "pauses.pauses_hist.global"
VIZ_PAUSES_TIMELINE = "pauses.pauses_timeline.global"
VIZ_MOMENTS_TIMELINE = "moments.moments_timeline.global"
VIZ_MOMENTUM_TIMESERIES = "momentum.momentum.global"

# Voice
VIZ_VOICE_TENSION_CURVE_GLOBAL = "voice_tension.tension_curve.global"
VIZ_VOICE_MISMATCH_SCATTER_GLOBAL = "voice_mismatch.sentiment_vs_arousal.global"
VIZ_VOICE_MISMATCH_TIMELINE_GLOBAL = "voice_mismatch.mismatch_timeline.global"
VIZ_VOICE_DRIFT_TIMELINE_SPEAKER = "voice_fingerprint.drift_timeline.speaker"
