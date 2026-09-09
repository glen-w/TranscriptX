"""Speaker auto-identification (voice + text patterns)."""

from transcriptx.core.speaker_profiles.identify.models import (
    ChannelCandidate,
    FusedDecision,
    IdentifyResult,
    SpeakerApplyResult,
)
from transcriptx.core.speaker_profiles.identify.service import (
    SpeakerIdentifyService,
    identify_many,
    maybe_identify_admitted,
)
from transcriptx.core.speaker_profiles.identify.settings import (
    IdentifySettings,
    load_identify_settings,
    save_identify_settings,
)

__all__ = [
    "ChannelCandidate",
    "FusedDecision",
    "IdentifyResult",
    "IdentifySettings",
    "SpeakerApplyResult",
    "SpeakerIdentifyService",
    "identify_many",
    "load_identify_settings",
    "maybe_identify_admitted",
    "save_identify_settings",
]
