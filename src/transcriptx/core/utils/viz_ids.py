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
VIZ_VOICE_PAUSES_DISTRIBUTION_GLOBAL = "voice.pauses_distribution.global"
VIZ_VOICE_PAUSES_DISTRIBUTION_SPEAKER = "voice.pauses_distribution.speaker"
VIZ_VOICE_PAUSES_TIMELINE_GLOBAL = "voice.pauses_timeline.global"
VIZ_VOICE_BURSTINESS_SPEAKER = "voice.burstiness.speaker"
VIZ_VOICE_HESITATION_MAP_GLOBAL = "voice.hesitation_map.global"
VIZ_VOICE_RHYTHM_COMPARE_GLOBAL = "voice.rhythm_compare.global"
VIZ_VOICE_RHYTHM_SCATTER_GLOBAL = "voice.rhythm_scatter.global"
VIZ_VOICE_F0_CONTOURS_SPEAKER = "voice.f0_contours.speaker"
VIZ_VOICE_F0_SLOPE_DISTRIBUTION_GLOBAL = (
    "voice.f0_slope_distribution.global"  # Prosody dashboard
)
VIZ_PROSODY_PROFILE_DISTRIBUTION_SPEAKER = (
    "prosody_dashboard.profile_distribution.speaker"
)
VIZ_PROSODY_PROFILE_CORR_SPEAKER = "prosody_dashboard.profile_corr.speaker"
VIZ_PROSODY_TIMELINE_GLOBAL = "prosody_dashboard.timeline.global"
VIZ_PROSODY_COMPARE_SPEAKERS_GLOBAL = "prosody_dashboard.compare_speakers.global"
VIZ_PROSODY_FINGERPRINT_SCATTER_GLOBAL = "prosody_dashboard.fingerprint_scatter.global"
VIZ_PROSODY_EGEMAPS_DISTRIBUTION_SPEAKER = (
    "prosody_dashboard.egemaps_distribution.speaker"
)
VIZ_PROSODY_QUALITY_SCATTER_GLOBAL = (
    "prosody_dashboard.quality_scatter.global"  # Affect tension
)
VIZ_AFFECT_TENSION_DERIVED_POLITE_TENSION_GLOBAL = (
    "affect_tension.derived_polite_tension.global"
)
VIZ_AFFECT_TENSION_DERIVED_SUPPRESSED_CONFLICT_GLOBAL = (
    "affect_tension.derived_suppressed_conflict.global"
)
VIZ_AFFECT_TENSION_DERIVED_INSTITUTIONAL_TONE_GLOBAL = (
    "affect_tension.derived_institutional_tone.global"
)
VIZ_AFFECT_TENSION_MISMATCH_RATE_GLOBAL = "affect_tension.mismatch_rate.global"
VIZ_AFFECT_TENSION_AVG_ENTROPY_GLOBAL = "affect_tension.avg_entropy.global"
VIZ_AFFECT_TENSION_AVG_VOLATILITY_GLOBAL = "affect_tension.avg_volatility.global"
VIZ_AFFECT_TENSION_ENTROPY_TIMESERIES_GLOBAL = (
    "affect_tension.entropy_timeseries.global"
)
VIZ_AFFECT_TENSION_VOLATILITY_TIMESERIES_GLOBAL = (
    "affect_tension.volatility_timeseries.global"
)
VIZ_AFFECT_TENSION_MISMATCH_TIMESERIES_GLOBAL = (
    "affect_tension.mismatch_timeseries.global"
)
VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_GLOBAL = (
    "affect_tension.entropy_volatility_timeseries.global"
)
VIZ_AFFECT_TENSION_ENTROPY_VOLATILITY_TIMESERIES_SPEAKER = (
    "affect_tension.entropy_volatility_timeseries.speaker"
)
VIZ_AFFECT_TENSION_MISMATCH_HEATMAP_GLOBAL = "affect_tension.mismatch_heatmap.global"
