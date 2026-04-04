from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.lazy_imports import optional_import  # type: ignore[import-untyped]

# Canonical eGeMAPS feature keys (short names used in eg_* columns)
EGEMAPS_CANONICAL_FIELDS: tuple[str, ...] = (
    "hnr_db",
    "jitter",
    "shimmer_db",
    "alpha_ratio",
    "hammarberg",
    "loudness",
)


def resolve_segment_id(segment: Dict[str, Any], transcript_key: str) -> str:
    """
    Resolve a stable segment identifier.

    This is load-bearing for joins/caching. We intentionally reuse the canonical
    logic used by the corrections subsystem.
    """

    from transcriptx.core.corrections.detect import (
        resolve_segment_id as _resolve_segment_id,
    )

    return str(_resolve_segment_id(segment, transcript_key))


@dataclass(frozen=True)
class VoiceFeatureRow:
    segment_id: str
    speaker: Optional[str]
    start_s: float
    end_s: float
    duration_s: float

    voiced_ratio: Optional[float] = None
    rms_db: Optional[float] = None

    f0_mean_hz: Optional[float] = None
    f0_std_hz: Optional[float] = None
    f0_range_semitones: Optional[float] = None

    speech_rate_wps: Optional[float] = None

    # Derived proxies (often computed downstream, but can be stored here too)
    arousal_raw: Optional[float] = None
    valence_raw: Optional[float] = None

    # Optional wide eGeMAPS features, stored as a dict of short names -> value.
    # These are expanded to flat `eg_*` columns in VoiceFeatureTable.to_frame().
    eg: Dict[str, float] = field(default_factory=dict)


@dataclass
class VoiceFeatureTable:
    rows: List[VoiceFeatureRow]

    def to_frame(self):  # -> pandas.DataFrame
        pd = optional_import("pandas", "voice feature tables")
        payload: list[dict[str, Any]] = []
        for row in self.rows:
            item = {
                "segment_id": row.segment_id,
                "speaker": row.speaker,
                "start_s": row.start_s,
                "end_s": row.end_s,
                "duration_s": row.duration_s,
                "voiced_ratio": row.voiced_ratio,
                "rms_db": row.rms_db,
                "f0_mean_hz": row.f0_mean_hz,
                "f0_std_hz": row.f0_std_hz,
                "f0_range_semitones": row.f0_range_semitones,
                "speech_rate_wps": row.speech_rate_wps,
                "arousal_raw": row.arousal_raw,
                "valence_raw": row.valence_raw,
            }
            for k, v in (row.eg or {}).items():
                item[f"eg_{k}"] = v
            payload.append(item)
        return pd.DataFrame(payload)

    @classmethod
    def from_frame(cls, df: Any) -> "VoiceFeatureTable":
        # df is a pandas DataFrame; avoid importing pandas here.
        rows: list[VoiceFeatureRow] = []
        eg_cols = [c for c in df.columns if isinstance(c, str) and c.startswith("eg_")]
        for _, r in df.iterrows():
            eg = {
                c.removeprefix("eg_"): float(r[c])
                for c in eg_cols
                if r.get(c) is not None
            }
            rows.append(
                VoiceFeatureRow(
                    segment_id=str(r.get("segment_id")),
                    speaker=(
                        None if r.get("speaker") is None else str(r.get("speaker"))
                    ),
                    start_s=float(r.get("start_s", 0.0)),
                    end_s=float(r.get("end_s", 0.0)),
                    duration_s=float(r.get("duration_s", 0.0)),
                    voiced_ratio=(
                        None
                        if r.get("voiced_ratio") is None
                        else float(r.get("voiced_ratio"))
                    ),
                    rms_db=(
                        None if r.get("rms_db") is None else float(r.get("rms_db"))
                    ),
                    f0_mean_hz=(
                        None
                        if r.get("f0_mean_hz") is None
                        else float(r.get("f0_mean_hz"))
                    ),
                    f0_std_hz=(
                        None
                        if r.get("f0_std_hz") is None
                        else float(r.get("f0_std_hz"))
                    ),
                    f0_range_semitones=(
                        None
                        if r.get("f0_range_semitones") is None
                        else float(r.get("f0_range_semitones"))
                    ),
                    speech_rate_wps=(
                        None
                        if r.get("speech_rate_wps") is None
                        else float(r.get("speech_rate_wps"))
                    ),
                    arousal_raw=(
                        None
                        if r.get("arousal_raw") is None
                        else float(r.get("arousal_raw"))
                    ),
                    valence_raw=(
                        None
                        if r.get("valence_raw") is None
                        else float(r.get("valence_raw"))
                    ),
                    eg=eg,
                )
            )
        return cls(rows=rows)
