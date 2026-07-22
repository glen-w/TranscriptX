"""Locked semantics versions, statuses, and detector defaults for topic_shift."""

from __future__ import annotations

from typing import Final, Literal

SCHEMA_VERSION: Final = "topic_shift_result_schema_v1"
PREPROCESSING_VERSION: Final = "topic_shift_preprocess_v1"

AnalyticalStatus = Literal[
    "success",
    "no_shift_detected",
    "insufficient_content",
    "unsupported_language",
    "backend_unavailable",
    "invalid_input",
]

BackendId = Literal[
    "transformers_en",
    "transformers_multi",
    "tfidf",
    "tfidf_char",
]

SEMANTICS_BY_BACKEND: Final[dict[str, str]] = {
    "transformers_en": "topic_shift_transformers_en_v1",
    "transformers_multi": "topic_shift_transformers_multi_v1",
    "tfidf": "topic_shift_tfidf_v1",
    "tfidf_char": "topic_shift_tfidf_char_v1",
}

# Detector geometry (shared; thresholds per-backend)
DEFAULT_WINDOW_SIZE: Final = 5
DEFAULT_STRIDE: Final = 2
DEFAULT_SMOOTH_WIDTH: Final = 3  # odd
DEFAULT_EDGE_EXCLUDE: Final = 1
DEFAULT_MIN_WINDOWS: Final = 4
DEFAULT_MIN_GAP_WINDOWS: Final = 2
DEFAULT_MIN_GAP_SECONDS: Final = 30.0
DEFAULT_MAX_SHIFTS: Final = 20
DEFAULT_CENTROID_RADIUS: Final = 2
DEFAULT_CENTROID_THRESHOLD: Final = 0.08
DEFAULT_FLOAT_DECIMALS: Final = 6
DEFAULT_MIN_TEXT_CHARS: Final = 8
DEFAULT_MAX_WINDOWS_PER_CHUNK: Final = 200
DEFAULT_CHUNK_OVERLAP_WINDOWS: Final = 20
DEFAULT_MIN_DURATION_FOR_RATE_SECONDS: Final = 120.0

# Per-backend threshold defaults
BACKEND_THRESHOLDS: Final[dict[str, dict[str, float]]] = {
    "transformers_en": {
        "k_mad": 3.0,
        "absolute_floor": 0.15,
        "min_prominence": 0.05,
    },
    "transformers_multi": {
        "k_mad": 3.0,
        "absolute_floor": 0.15,
        "min_prominence": 0.05,
    },
    "tfidf": {
        "k_mad": 2.5,
        "absolute_floor": 0.20,
        "min_prominence": 0.08,
    },
    "tfidf_char": {
        "k_mad": 2.0,
        "absolute_floor": 0.25,
        "min_prominence": 0.10,
    },
}

DEFAULT_EN_MODEL: Final = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MULTI_MODEL: Final = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

ENGLISH_CODES: Final = frozenset({"en", "eng", "en-us", "en-gb", "en_us", "en_gb"})
