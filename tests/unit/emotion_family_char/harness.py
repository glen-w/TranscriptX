"""Deterministic characterization helpers for emotion-family producers.

Fixtures under ``tests/fixtures/emotion_family/characterization/`` must be
generated from committed test doubles — never live Hugging Face / NRC output.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence
from unittest.mock import MagicMock, patch

from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
from transcriptx.core.analysis.emotion import EmotionAnalysis
from transcriptx.core.analysis.emotion.preflight import LexicalPreflightResult
from transcriptx.core.analysis.fine_grained_emotion import FineGrainedEmotionAnalysis
from transcriptx.core.analysis.hf_text_classification.profiles import (
    CONTEXTUAL_HARTMANN_V1,
    FINE_GRAINED_GOEMOTIONS_V1,
)
from transcriptx.core.analysis.hf_text_classification.runtime import (
    LoadedClassifier,
    ScoreResult,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "emotion_family"
    / "characterization"
)
UPDATE_GOLDENS = os.environ.get("UPDATE_EMOTION_FAMILY_CHARACTERIZATION") == "1"

# Pinned attempt / inference ids (32-hex).
ARTIFACT_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CACHED_INFERENCE_ID = "cccccccccccccccccccccccccccccccc"

# JSON-pointer allowlist: strip only these attempt-id embeddings for deep-eq.
# Never recursively strip every key containing "generation".
STRIP_POINTERS = (
    "/artifact_generation_id",
    # Nested refs inside pending projections (serialized form below).
    "/_pending_projections/*/projection/canonical_ref/artifact_generation_id",
    "/_pending_projections/*/projection/contextual_emotion_canonical_ref/artifact_generation_id",
    "/_pending_projections/*/projection/fine_grained_emotion_canonical_ref/artifact_generation_id",
    "/_pending_projections/*/projection/emotion_canonical_ref/artifact_generation_id",
    "/sample_projection/canonical_ref/artifact_generation_id",
    "/sample_projection/contextual_emotion_canonical_ref/artifact_generation_id",
)


def _loaded(profile) -> LoadedClassifier:
    id2label = {i: lab for i, lab in enumerate(profile.labels)}
    return LoadedClassifier(
        profile=profile,
        model=MagicMock(),
        tokenizer=MagicMock(),
        device="cpu",
        device_class="cpu",
        dtype="float32",
        cache_key="char-cache-key",
        effective_max_length=64,
        resolved_label_map_hash="char-label-map-hash",
        resolved_id2label=id2label,
    )


def _softmax_scores(label: str) -> dict[str, float]:
    scores = {lab: 0.02 for lab in CONTEXTUAL_HARTMANN_V1.labels}
    remaining = 1.0 - 0.02 * (len(scores) - 1)
    scores[label] = remaining
    return scores


def _sigmoid_scores(*high: str) -> dict[str, float]:
    scores = {lab: 0.01 for lab in FINE_GRAINED_GOEMOTIONS_V1.labels}
    for lab in high:
        scores[lab] = 0.80
    scores["neutral"] = 0.05
    return scores


def _score_result(scores: Mapping[str, float]) -> ScoreResult:
    return ScoreResult(
        scores=dict(scores),
        truncated=False,
        omitted_token_count_lower_bound=0,
        device_class="cpu",
        dtype="float32",
    )


def _uuid_hex_factory(value: str):
    class _UUID:
        hex = value

    def _factory(*_a, **_k):
        return _UUID()

    return _factory


def serialize_analyze_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Make analyze() output JSON-serializable without dropping gen-id relationships."""
    out = copy.deepcopy(dict(result))
    # Drop live segment object lists (identity checked separately in adoption tests).
    for key in (
        "segments",
        "segments_with_emotion",
        "segments_with_contextual_emotion",
        "segments_with_fine_grained_emotion",
    ):
        out.pop(key, None)
    pending = out.get("_pending_projections")
    if isinstance(pending, list):
        serialized = []
        for entry in pending:
            if isinstance(entry, (tuple, list)) and len(entry) == 2:
                seg, proj = entry
                sid = str(
                    (seg or {}).get("id")
                    or (seg or {}).get("segment_id")
                    or (proj or {}).get("segment_id")
                    or ""
                )
                serialized.append(
                    {
                        "segment_id": sid,
                        "projection": copy.deepcopy(dict(proj or {})),
                    }
                )
            else:
                serialized.append(copy.deepcopy(entry))
        out["_pending_projections"] = serialized
    return out


def _pointer_tokens(pointer: str) -> list[str]:
    return [p for p in pointer.split("/") if p]


def _strip_pointer(obj: Any, tokens: Sequence[str]) -> None:
    if not tokens:
        return
    head, *rest = tokens
    if head == "*":
        if isinstance(obj, list):
            for item in obj:
                _strip_pointer(item, rest)
        elif isinstance(obj, dict):
            for item in obj.values():
                _strip_pointer(item, rest)
        return
    if isinstance(obj, dict) and head in obj:
        if not rest:
            obj.pop(head, None)
        else:
            _strip_pointer(obj[head], rest)


def normalize_for_deep_eq(serialized: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-eq shape: strip allowlisted attempt-id embeddings only."""
    data = copy.deepcopy(dict(serialized))
    for pointer in STRIP_POINTERS:
        _strip_pointer(data, _pointer_tokens(pointer))
    # On miss paths inference_generation_id equals artifact id; strip top-level
    # inference id only when it matches the (already stripped) artifact pattern
    # by also stripping /inference_generation_id from deep-eq — relationship
    # asserts cover both keys separately.
    data.pop("inference_generation_id", None)
    return data


def assert_generation_id_relationships(
    raw: Mapping[str, Any],
    *,
    expect_cache_hit: bool,
    cached_inference_id: str | None = None,
) -> None:
    artifact = raw.get("artifact_generation_id")
    inference = raw.get("inference_generation_id")
    assert isinstance(artifact, str) and len(artifact) == 32
    assert isinstance(inference, str) and len(inference) == 32
    if expect_cache_hit:
        assert cached_inference_id is not None
        assert inference == cached_inference_id
        assert artifact != inference
    else:
        # Miss / failure: today both equal the attempt id.
        assert inference == artifact


def write_golden(name: str, payload: Mapping[str, Any]) -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{name}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_golden(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_matches_golden(name: str, serialized: Mapping[str, Any]) -> None:
    normalized = normalize_for_deep_eq(serialized)
    path = FIXTURES_DIR / f"{name}.json"
    if UPDATE_GOLDENS or not path.exists():
        write_golden(name, normalized)
    expected = load_golden(name)
    assert normalized == expected, f"characterization drift for {name}"


# --- segment factories -------------------------------------------------------


def segs_success() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I am delighted",
            "start": 0.0,
            "end": 1.0,
            "language": "en",
        },
        {
            "id": "2",
            "speaker": "Bob",
            "text": "I am furious",
            "start": 1.0,
            "end": 2.0,
            "language": "en",
        },
    ]


def segs_empty() -> list[dict[str, Any]]:
    return []


def segs_mixed_language() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "Hello there",
            "start": 0.0,
            "end": 1.0,
            "language": "en",
        },
        {
            "id": "2",
            "speaker": "Bob",
            "text": "Bonjour ami",
            "start": 1.0,
            "end": 2.0,
            "language": "fr",
        },
    ]


def segs_whitespace_en() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "   ",
            "start": 0.0,
            "end": 1.0,
            "language": "en",
        }
    ]


def segs_whitespace_fr() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "   ",
            "start": 0.0,
            "end": 1.0,
            "language": "fr",
        }
    ]


def segs_missing_text() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "speaker": "Alice",
            "start": 0.0,
            "end": 1.0,
            "language": "en",
        }
    ]


# --- runners -----------------------------------------------------------------


def _cache_root_patches(module: str, tmp_path: Path):
    inf = tmp_path / "cache" / "emotion_family" / module
    agg = inf / "aggregation"
    return (
        patch(
            f"transcriptx.core.analysis.{module}.default_inference_cache_root",
            return_value=inf,
        ),
        patch(
            f"transcriptx.core.analysis.{module}.default_aggregation_cache_root",
            return_value=agg,
        ),
    )


def run_contextual(
    segments: list[dict[str, Any]],
    *,
    tmp_path: Path,
    score_fn: Callable | None = None,
    load_side_effect: Exception | None = None,
    score_side_effect: Exception | None = None,
    score_return: Sequence[ScoreResult] | None = None,
    uuid_hex: str = ARTIFACT_ID,
) -> dict[str, Any]:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            contextual_emotion=SimpleNamespace(
                profile_id=CONTEXTUAL_HARTMANN_V1.profile_id,
                confidence_threshold=0.3,
                batch_size=8,
            )
        )
    )
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    n = sum(
        1
        for s in segments
        if (s.get("text") or "").strip()
        and str(s.get("language") or "en").casefold().startswith("en")
    )
    if score_return is None and score_side_effect is None and score_fn is None:
        score_return = [
            _score_result(_softmax_scores("joy" if i % 2 == 0 else "anger"))
            for i in range(n)
        ]

    load_patch = (
        {"side_effect": load_side_effect}
        if load_side_effect is not None
        else {"return_value": loaded}
    )
    score_kwargs: dict[str, Any] = {}
    if score_side_effect is not None:
        score_kwargs["side_effect"] = score_side_effect
    elif score_fn is not None:
        score_kwargs["side_effect"] = score_fn
    else:
        score_kwargs["return_value"] = list(score_return or [])

    inf_p, agg_p = _cache_root_patches("contextual_emotion", tmp_path)
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.contextual_emotion.load_classifier",
            **load_patch,
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.score_texts",
            **score_kwargs,
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.library_versions",
            return_value={"transformers_version": "0.0", "torch_version": "0.0"},
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.uuid.uuid4",
            side_effect=_uuid_hex_factory(uuid_hex),
        ),
        inf_p,
        agg_p,
    ):
        return ContextualEmotionAnalysis().analyze(segments)


def run_fine_grained(
    segments: list[dict[str, Any]],
    *,
    tmp_path: Path,
    score_fn: Callable | None = None,
    load_side_effect: Exception | None = None,
    score_side_effect: Exception | None = None,
    score_return: Sequence[ScoreResult] | None = None,
    uuid_hex: str = ARTIFACT_ID,
) -> dict[str, Any]:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            fine_grained_emotion=SimpleNamespace(
                profile_id=FINE_GRAINED_GOEMOTIONS_V1.profile_id,
                label_threshold=0.3,
                max_labels_per_segment=3,
                batch_size=8,
            )
        )
    )
    loaded = _loaded(FINE_GRAINED_GOEMOTIONS_V1)
    n = sum(
        1
        for s in segments
        if (s.get("text") or "").strip()
        and str(s.get("language") or "en").casefold().startswith("en")
    )
    if score_return is None and score_side_effect is None and score_fn is None:
        score_return = [
            _score_result(_sigmoid_scores("joy", "gratitude")) for _ in range(n)
        ]

    load_patch = (
        {"side_effect": load_side_effect}
        if load_side_effect is not None
        else {"return_value": loaded}
    )
    score_kwargs: dict[str, Any] = {}
    if score_side_effect is not None:
        score_kwargs["side_effect"] = score_side_effect
    elif score_fn is not None:
        score_kwargs["side_effect"] = score_fn
    else:
        score_kwargs["return_value"] = list(score_return or [])

    inf_p, agg_p = _cache_root_patches("fine_grained_emotion", tmp_path)
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.load_classifier",
            **load_patch,
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.score_texts",
            **score_kwargs,
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.library_versions",
            return_value={"transformers_version": "0.0", "torch_version": "0.0"},
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.uuid.uuid4",
            side_effect=_uuid_hex_factory(uuid_hex),
        ),
        inf_p,
        agg_p,
    ):
        return FineGrainedEmotionAnalysis().analyze(segments)


class _FakeNRCLex:
    """Minimal NRCLex stand-in for offline lexical characterization."""

    def __init__(self, text: str = ""):
        self.text = text or ""
        self.affect_dict = {
            "delighted": ["joy", "positive"],
            "furious": ["anger", "negative"],
            "hello": ["joy"],
            "there": [],
        }


def run_lexical(
    segments: list[dict[str, Any]],
    *,
    tmp_path: Path,
    preflight: LexicalPreflightResult | None = None,
    uuid_hex: str = ARTIFACT_ID,
    force_empty_lexicon: bool = False,
) -> dict[str, Any]:
    if preflight is None:
        preflight = LexicalPreflightResult(True, "ok", nrclex_version="3.0.0")

    lexicon = (
        {}
        if force_empty_lexicon
        else {
            "delighted": ["joy", "positive"],
            "furious": ["anger", "negative"],
            "hello": ["joy"],
            "bonjour": ["joy"],
            "ami": [],
        }
    )

    inf = tmp_path / "cache" / "emotion_family" / "emotion"
    agg = inf / "aggregation"
    with (
        patch(
            "transcriptx.core.analysis.emotion.run_lexical_preflight",
            return_value=preflight,
        ),
        patch(
            "transcriptx.core.analysis.emotion.build_lexicon_from_nrclex",
            return_value=lexicon,
        ),
        patch(
            "transcriptx.core.analysis.emotion.uuid.uuid4",
            side_effect=_uuid_hex_factory(uuid_hex),
        ),
        patch(
            "transcriptx.core.analysis.emotion.default_inference_cache_root",
            return_value=inf,
        ),
        patch(
            "transcriptx.core.analysis.emotion.default_aggregation_cache_root",
            return_value=agg,
        ),
        patch.dict("sys.modules", {"nrclex": MagicMock(NRCLex=_FakeNRCLex)}),
    ):
        return EmotionAnalysis().analyze(copy.deepcopy(segments))
