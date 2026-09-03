# Emotion group charts: pooled single view

## Inputs

- **`emotion_pooled`** on `chart_outcome`: `emotion_scores` = **unweighted mean** of each transcript’s `global_emotions` profile (one value per emotion key per transcript, then averaged across transcripts).

## Chart

- `group.emotion.pooled.profile.global` — bar over canonical emotion labels present in the pooled dict.

## Not

- Not weighted by segment count or duration (explicit choice; see aggregation).
- Session bars and temporal overlay remain separate families.
- Fail closed if `emotion_pooled` missing or `emotion_scores` empty.
