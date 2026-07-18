"""Built-in pinned emotion classifier profiles (experimental until Phase 5)."""

from __future__ import annotations

from transcriptx.core.analysis.hf_text_classification.runtime import ModelProfile

# Immutable Hub commit SHAs (resolved 2026-07-18). Floating tags forbidden.
THRESHOLD_PROFILE_PROVISIONAL_V0 = "threshold_profile_provisional_v0"

CONTEXTUAL_HARTMANN_REVISION = "0e1cd914e3d46199ed785853e12b57304e04178b"
FINE_GRAINED_GOEMOTIONS_REVISION = "d75048347613a25d77de8cf6412eaae9fa7b26be"

CONTEXTUAL_HARTMANN_V1 = ModelProfile(
    profile_id="contextual_hartmann_distilroberta_v1",
    model_id="j-hartmann/emotion-english-distilroberta-base",
    model_revision=CONTEXTUAL_HARTMANN_REVISION,
    tokenizer_id="j-hartmann/emotion-english-distilroberta-base",
    tokenizer_revision=CONTEXTUAL_HARTMANN_REVISION,
    activation="softmax",
    labels=(
        "anger",
        "disgust",
        "fear",
        "joy",
        "neutral",
        "sadness",
        "surprise",
    ),
    threshold_profile_version=THRESHOLD_PROFILE_PROVISIONAL_V0,
    release_channel="experimental",
    # Pinned revision ships pytorch_model.bin only (no model.safetensors).
    prefer_safetensors=False,
    max_length=256,
    licence="Apache-2.0",
)

FINE_GRAINED_GOEMOTIONS_V1 = ModelProfile(
    profile_id="fine_grained_samlowe_go_emotions_v1",
    model_id="SamLowe/roberta-base-go_emotions",
    model_revision=FINE_GRAINED_GOEMOTIONS_REVISION,
    tokenizer_id="SamLowe/roberta-base-go_emotions",
    tokenizer_revision=FINE_GRAINED_GOEMOTIONS_REVISION,
    activation="sigmoid",
    labels=(
        "admiration",
        "amusement",
        "anger",
        "annoyance",
        "approval",
        "caring",
        "confusion",
        "curiosity",
        "desire",
        "disappointment",
        "disapproval",
        "disgust",
        "embarrassment",
        "excitement",
        "fear",
        "gratitude",
        "grief",
        "joy",
        "love",
        "nervousness",
        "optimism",
        "pride",
        "realization",
        "relief",
        "remorse",
        "sadness",
        "surprise",
        "neutral",
    ),
    threshold_profile_version=THRESHOLD_PROFILE_PROVISIONAL_V0,
    release_channel="experimental",
    max_length=256,
    licence="MIT",
)

BUILTIN_PROFILES: dict[str, ModelProfile] = {
    CONTEXTUAL_HARTMANN_V1.profile_id: CONTEXTUAL_HARTMANN_V1,
    FINE_GRAINED_GOEMOTIONS_V1.profile_id: FINE_GRAINED_GOEMOTIONS_V1,
}


def get_builtin_profile(profile_id: str) -> ModelProfile:
    try:
        return BUILTIN_PROFILES[profile_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown emotion model profile {profile_id!r}; "
            f"v1 allows only built-in profiles: {sorted(BUILTIN_PROFILES)}"
        ) from exc
