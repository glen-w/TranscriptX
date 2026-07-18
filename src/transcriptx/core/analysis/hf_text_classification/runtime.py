"""Shared Hugging Face text-classification runtime (no pipeline() for scoring)."""

from __future__ import annotations

import hashlib
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from transcriptx.core.analysis.emotion_family.canonical_hash import canonical_json_hash
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

Activation = Literal["softmax", "sigmoid"]
LONG_TEXT_POLICY_V1 = "long_text_policy_v1"
# v2: truncation exposes omitted_token_count_lower_bound (not an exact count).
LONG_TEXT_POLICY_V2 = "long_text_policy_v2"
NUMERICAL_DTYPE_V1 = "float32"
_FLOATING_REVISIONS = frozenset({"", "main", "latest", "master", "HEAD"})
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_CACHE_LOCK = threading.RLock()
_LOADING_LOCKS: dict[str, threading.Lock] = {}
_MODEL_CACHE: OrderedDict[str, "LoadedClassifier"] = OrderedDict()
_MAX_CACHE_SLOTS = 2


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    activation: Activation
    labels: tuple[str, ...]
    threshold_profile_version: str
    release_channel: str = "experimental"
    prefer_safetensors: bool = True
    max_length: int = 256
    licence: str = ""

    @property
    def num_labels(self) -> int:
        return len(self.labels)

    @property
    def label_map_hash(self) -> str:
        return canonical_json_hash(
            {"labels": list(self.labels), "activation": self.activation}
        )


@dataclass
class ScoreResult:
    scores: dict[str, float]
    truncated: bool
    omitted_token_count_lower_bound: int
    device_class: str
    dtype: str
    warnings: list[str] = field(default_factory=list)

    @property
    def omitted_token_count(self) -> int:
        """Deprecated alias for omitted_token_count_lower_bound."""
        return self.omitted_token_count_lower_bound


@dataclass
class LoadedClassifier:
    profile: ModelProfile
    model: Any
    tokenizer: Any
    device: Any
    device_class: str
    dtype: Any
    cache_key: str
    effective_max_length: int
    resolved_label_map_hash: str
    resolved_id2label: dict[int, str]


def device_class_for(device: Any) -> str:
    s = str(device).lower()
    if "cuda" in s:
        return "cuda"
    if "mps" in s:
        return "mps"
    if "cpu" in s:
        return "cpu"
    return "other"


def _cache_key(profile: ModelProfile, device_class: str, dtype_name: str) -> str:
    raw = "|".join(
        [
            profile.profile_id,
            profile.model_id,
            profile.model_revision,
            profile.tokenizer_id,
            profile.tokenizer_revision,
            profile.activation,
            device_class,
            dtype_name,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolve_device(torch_mod: Any) -> tuple[Any, str, str | None]:
    """Return (device, device_class, fallback_reason)."""
    try:
        if torch_mod.cuda.is_available():
            return torch_mod.device("cuda"), "cuda", None
    except Exception:
        pass
    try:
        mps = getattr(torch_mod.backends, "mps", None)
        if mps is not None and mps.is_available():
            return torch_mod.device("mps"), "mps", None
    except Exception:
        pass
    return torch_mod.device("cpu"), "cpu", None


def assert_revision_pinned(profile: ModelProfile) -> None:
    """Refuse floating Hub revisions / tags; require full 40-char commit SHAs."""
    for rev in (profile.model_revision, profile.tokenizer_revision):
        rev_s = str(rev).strip()
        if rev_s in _FLOATING_REVISIONS or not _COMMIT_SHA_RE.fullmatch(rev_s):
            raise RuntimeError(
                f"profile {profile.profile_id!r} forbids floating revision "
                f"{rev!r}; pin an immutable Hub commit SHA (40 hex chars)"
            )


def assert_stable_revision_pinned(profile: ModelProfile) -> None:
    """Backward-compatible alias; all builtin loads require pinned SHAs."""
    assert_revision_pinned(profile)


def _positional_limit_from_model(model: Any | None) -> int | None:
    if model is None:
        return None
    config = getattr(model, "config", None)
    if config is None:
        return None
    for attr in ("max_position_embeddings", "n_positions", "max_sequence_length"):
        value = getattr(config, attr, None)
        if isinstance(value, int) and 0 < value < 10_000_000:
            return int(value)
    return None


def resolve_usable_max_length(
    tokenizer: Any,
    profile_max: int,
    *,
    model: Any | None = None,
) -> int:
    """Resolve safe max_length from tokenizer and model positional limits."""
    usable = int(profile_max)
    model_max = getattr(tokenizer, "model_max_length", None)
    if isinstance(model_max, int) and 0 < model_max < 10_000_000:
        usable = min(usable, int(model_max))
    positional = _positional_limit_from_model(model)
    if positional is not None:
        usable = min(usable, positional)
    return max(1, usable)


def _resolved_id2label(model: Any) -> dict[int, str]:
    return {int(k): str(v).casefold() for k, v in model.config.id2label.items()}


def _validate_indexed_label_map(profile: ModelProfile, id2label: dict[int, str]) -> str:
    expected = [lab.casefold() for lab in profile.labels]
    if len(id2label) != profile.num_labels:
        raise RuntimeError(
            f"num_labels mismatch for {profile.profile_id}: "
            f"expected {profile.num_labels}, got {len(id2label)}"
        )
    for i, expected_label in enumerate(expected):
        got = id2label.get(i)
        if got != expected_label:
            raise RuntimeError(
                f"label index mismatch for {profile.profile_id} at index {i}: "
                f"expected {expected_label!r}, got {got!r}"
            )
    return canonical_json_hash(
        {
            "labels": [id2label[i] for i in range(len(expected))],
            "activation": profile.activation,
        }
    )


def _release_accelerator_memory(torch_mod: Any, device_class: str) -> None:
    try:
        if device_class == "cuda" and hasattr(torch_mod, "cuda"):
            torch_mod.cuda.empty_cache()
        elif device_class == "mps":
            mps = getattr(torch_mod, "mps", None)
            if mps is not None and hasattr(mps, "empty_cache"):
                mps.empty_cache()
    except Exception:
        pass


def _evict_one(torch_mod: Any | None = None) -> None:
    """LRU eviction with accelerator cleanup."""
    if not _MODEL_CACHE:
        return
    evict_key, evicted = _MODEL_CACHE.popitem(last=False)
    dclass = getattr(evicted, "device_class", "cpu")
    try:
        del evicted.model
        del evicted.tokenizer
    except Exception:
        pass
    del evicted
    if torch_mod is not None:
        _release_accelerator_memory(torch_mod, dclass)
    _LOADING_LOCKS.pop(evict_key, None)


def _loading_lock_for(key: str) -> threading.Lock:
    with _CACHE_LOCK:
        lock = _LOADING_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOADING_LOCKS[key] = lock
        return lock


def load_classifier(profile: ModelProfile) -> LoadedClassifier:
    """Load and validate a built-in profile; thread-safe bounded LRU cache."""
    from transcriptx.core.utils.downloads import downloads_disabled
    from transcriptx.core.utils.lazy_imports import get_torch, get_transformers

    assert_revision_pinned(profile)

    torch = get_torch()
    transformers = get_transformers()
    device, dclass, _fallback = resolve_device(torch)
    dtype = torch.float32
    key = _cache_key(profile, dclass, "float32")

    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            _MODEL_CACHE.move_to_end(key)
            return cached

    load_lock = _loading_lock_for(key)
    with load_lock:
        with _CACHE_LOCK:
            cached = _MODEL_CACHE.get(key)
            if cached is not None:
                _MODEL_CACHE.move_to_end(key)
                return cached

        local_only = bool(downloads_disabled())
        common_kw = dict(
            local_files_only=local_only,
            trust_remote_code=False,
        )
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            profile.tokenizer_id,
            revision=profile.tokenizer_revision,
            **common_kw,
        )
        try:
            model = transformers.AutoModelForSequenceClassification.from_pretrained(
                profile.model_id,
                revision=profile.model_revision,
                use_safetensors=profile.prefer_safetensors,
                torch_dtype=dtype,
                **common_kw,
            )
        except TypeError:
            model = transformers.AutoModelForSequenceClassification.from_pretrained(
                profile.model_id,
                revision=profile.model_revision,
                torch_dtype=dtype,
                **common_kw,
            )

        id2label = _resolved_id2label(model)
        resolved_hash = _validate_indexed_label_map(profile, id2label)
        effective_max = resolve_usable_max_length(
            tokenizer, profile.max_length, model=model
        )

        model.to(device=device, dtype=dtype)
        # Validate resolved parameter dtype matches claimed numerical profile
        for param in model.parameters():
            if param.dtype != dtype:
                raise RuntimeError(
                    f"model dtype {param.dtype} != required float32 for "
                    f"{profile.profile_id}"
                )
            break
        model.eval()
        loaded = LoadedClassifier(
            profile=profile,
            model=model,
            tokenizer=tokenizer,
            device=device,
            device_class=dclass,
            dtype=dtype,
            cache_key=key,
            effective_max_length=effective_max,
            resolved_label_map_hash=resolved_hash,
            resolved_id2label=dict(id2label),
        )

        with _CACHE_LOCK:
            if key in _MODEL_CACHE:
                _MODEL_CACHE.move_to_end(key)
                return _MODEL_CACHE[key]
            while len(_MODEL_CACHE) >= _MAX_CACHE_SLOTS:
                _evict_one(torch)
            _MODEL_CACHE[key] = loaded
            _MODEL_CACHE.move_to_end(key)
        return loaded


def score_texts(
    loaded: LoadedClassifier,
    texts: Sequence[str],
    *,
    max_length: int | None = None,
) -> list[ScoreResult]:
    """Batched forward pass with softmax or sigmoid per profile."""
    from transcriptx.core.utils.lazy_imports import get_torch

    torch = get_torch()
    if not texts:
        return []

    if max_length is None:
        ml = int(loaded.effective_max_length)
    else:
        ml = int(max_length)
    ml = min(ml, loaded.effective_max_length)
    ml = max(1, ml)
    tok = loaded.tokenizer
    model = loaded.model
    device = loaded.device

    # Bounded truncation accounting: encode with truncate at ml, and probe
    # overflow with a single extra-token window rather than unbounded tokenize.
    # omitted_token_count_lower_bound is 1 when truncated (policy v2), not exact.
    truncated_flags: list[bool] = []
    omitted: list[int] = []
    for text in texts:
        probe = tok(
            text,
            add_special_tokens=True,
            truncation=True,
            max_length=ml + 1,
            return_overflowing_tokens=False,
        )
        probe_len = len(probe["input_ids"])
        truncated = probe_len > ml
        truncated_flags.append(truncated)
        omitted.append(1 if truncated else 0)

    enc = tok(
        list(texts),
        padding=True,
        truncation=True,
        max_length=ml,
        return_tensors="pt",
    )
    enc = {
        k: v.to(device)
        for k, v in enc.items()
        if k in {"input_ids", "attention_mask", "token_type_ids"}
    }

    try:
        with torch.inference_mode():
            outputs = model(**enc)
            logits = outputs.logits
            if loaded.profile.activation == "softmax":
                probs = torch.nn.functional.softmax(logits.float(), dim=-1)
            else:
                probs = torch.sigmoid(logits.float())
            probs_cpu = probs.detach().cpu()
    except RuntimeError as exc:
        if "out of memory" not in str(exc).lower():
            raise
        # v1: fail closed — never mutate a GPU-keyed cache onto CPU mid-run.
        raise RuntimeError(
            f"OOM on device {loaded.device_class}; refusing CPU fallback to "
            "preserve analytical provenance (device_class in fingerprint)"
        ) from exc

    id2label = loaded.resolved_id2label or {
        int(k): str(v).casefold() for k, v in model.config.id2label.items()
    }
    results: list[ScoreResult] = []
    for i in range(len(texts)):
        row = probs_cpu[i]
        scores = {
            id2label.get(j, str(j)): float(row[j].item()) for j in range(row.shape[0])
        }
        results.append(
            ScoreResult(
                scores=scores,
                truncated=truncated_flags[i],
                omitted_token_count_lower_bound=omitted[i],
                device_class=loaded.device_class,
                dtype="float32",
                warnings=[],
            )
        )
    return results


def clear_model_cache() -> None:
    with _CACHE_LOCK:
        keys = list(_MODEL_CACHE.keys())
        for key in keys:
            _MODEL_CACHE.pop(key, None)
        _LOADING_LOCKS.clear()
