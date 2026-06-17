"""Canonical TRANSCRIPTX_* environment override application."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Literal

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.logger import log_warning

InvalidPolicy = Literal["skip", "warn_skip", "raise"]
CoercionResult = tuple[bool, Any | None]
Coercer = Callable[[str], CoercionResult]

TRUTHY_VALUES = frozenset(("1", "true", "yes", "on"))
FALSY_VALUES = frozenset(("0", "false", "no", "off"))

LEGACY_REJECTED_KEYS = (
    "TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED",
    "TRANSCRIPTX_AUDIO_DENOISE_ENABLED",
    "TRANSCRIPTX_AUDIO_HIGHPASS_ENABLED",
)

# TRANSCRIPTX_* keys used by other surfaces and not part of config env overrides.
INFRA_ENV_ALLOWLIST = frozenset(
    {
        "TRANSCRIPTX_CONFIG_STRICT",
        "TRANSCRIPTX_DATA_DIR",
        "TRANSCRIPTX_CONFIG_DIR",
        "TRANSCRIPTX_PROFILES_DIR",
        "TRANSCRIPTX_TRANSCRIPTS_DIR",
        "TRANSCRIPTX_RECORDINGS_DIR",
        "TRANSCRIPTX_OUTPUT_DIR",
        "TRANSCRIPTX_WAV_BACKUP_DIR",
        "TRANSCRIPTX_WAV_STORAGE_DIR",
        "TRANSCRIPTX_IMPORTS_DIR",
        "TRANSCRIPTX_NO_AUTO_INSTALL",
        "TRANSCRIPTX_DISABLE_DOWNLOADS",
        "TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD",
        "TRANSCRIPTX_SPACY_MODEL",
        "TRANSCRIPTX_HOST",
        "TRANSCRIPTX_PORT",
        "TRANSCRIPTX_MPL_MAX_OPEN_WARNING",
        "TRANSCRIPTX_ENABLE_CORRECTIONS_STUDIO",
        "TRANSCRIPTX_CACHE_DIR",
        "TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS",
        "TRANSCRIPTX_TORCH_VARIANT",
    }
)


@dataclass(frozen=True)
class EnvKey:
    """Declarative environment key contract."""

    env_name: str
    target_path: tuple[str, ...]
    coercer: Coercer
    allowed_values: frozenset[str] | None = None
    invalid_policy: InvalidPolicy = "skip"
    post_hook_target: tuple[str, ...] | None = None
    post_hook_method: str | None = None


def _normalize(raw: str) -> str:
    return raw.strip().lower()


def coerce_int(raw: str) -> CoercionResult:
    try:
        return (True, int(raw.strip()))
    except (TypeError, ValueError):
        return (False, None)


def coerce_float(raw: str) -> CoercionResult:
    try:
        return (True, float(raw.strip()))
    except (TypeError, ValueError):
        return (False, None)


def coerce_str(raw: str) -> CoercionResult:
    value = raw.strip()
    if not value:
        return (False, None)
    return (True, value)


def coerce_lower_strip(raw: str) -> CoercionResult:
    value = _normalize(raw)
    if not value:
        return (False, None)
    return (True, value)


def coerce_bool_on_off(raw: str) -> CoercionResult:
    # Preserve existing semantics: any non-truthy non-empty value maps to False.
    value = _normalize(raw)
    if not value:
        return (False, None)
    return (True, value in TRUTHY_VALUES)


def coerce_tri_state_bool_fallback(raw: str) -> CoercionResult:
    value = _normalize(raw)
    if not value:
        return (False, None)
    if value in ("auto", "suggest", "off"):
        return (True, value)
    if value in TRUTHY_VALUES:
        return (True, "auto")
    if value in FALSY_VALUES:
        return (True, "off")
    return (False, None)


def coerce_json_or_csv_list(raw: str) -> CoercionResult:
    value = raw.strip()
    if not value:
        return (False, None)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            cleaned = [str(item).strip() for item in parsed if str(item).strip()]
            return (True, cleaned) if cleaned else (False, None)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    cleaned = [item.strip() for item in value.split(",") if item.strip()]
    return (True, cleaned) if cleaned else (False, None)


def _env_key(
    env_name: str,
    target_path: tuple[str, ...],
    coercer: Coercer,
    *,
    allowed_values: tuple[str, ...] | None = None,
    invalid_policy: InvalidPolicy = "skip",
    post_hook_target: tuple[str, ...] | None = None,
    post_hook_method: str | None = None,
) -> EnvKey:
    return EnvKey(
        env_name=env_name,
        target_path=target_path,
        coercer=coercer,
        allowed_values=frozenset(allowed_values) if allowed_values else None,
        invalid_policy=invalid_policy,
        post_hook_target=post_hook_target,
        post_hook_method=post_hook_method,
    )


ENV_KEY_REGISTRY: tuple[EnvKey, ...] = (
    _env_key("TRANSCRIPTX_CORE", ("core_mode",), coerce_bool_on_off),
    _env_key(
        "TRANSCRIPTX_SENTIMENT_WINDOW_SIZE",
        ("analysis", "sentiment_window_size"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_EMOTION_MODEL", ("analysis", "emotion_model_name"), coerce_str
    ),
    _env_key(
        "TRANSCRIPTX_SEMANTIC_MODEL", ("analysis", "semantic_model_name"), coerce_str
    ),
    _env_key(
        "TRANSCRIPTX_SEMANTIC_V2_MODEL",
        ("analysis", "semantic_similarity_v2", "model_name"),
        coerce_str,
    ),
    _env_key(
        "TRANSCRIPTX_SENTIMENT_BACKEND",
        ("analysis", "sentiment_backend"),
        coerce_lower_strip,
        allowed_values=("vader", "transformers", "textblob"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL",
        ("analysis", "bertopic", "embedding_model"),
        coerce_str,
    ),
    _env_key(
        "TRANSCRIPTX_SEMANTIC_PROGRESS_LOG_INTERVAL_SECONDS",
        ("analysis", "semantic_progress_log_interval_seconds"),
        coerce_float,
    ),
    _env_key(
        "TRANSCRIPTX_MODULE_PROGRESS_LOG_INTERVAL_SECONDS",
        ("analysis", "module_progress_log_interval_seconds"),
        coerce_float,
    ),
    _env_key(
        "TRANSCRIPTX_ACTS_MODEL", ("analysis", "acts", "ml_model_name"), coerce_str
    ),
    _env_key(
        "TRANSCRIPTX_WORDCLOUD_MAX_WORDS",
        ("analysis", "wordcloud_max_words"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_WAV_FOLDERS", ("input", "wav_folders"), coerce_json_or_csv_list
    ),
    _env_key(
        "TRANSCRIPTX_RECORDINGS_FOLDERS",
        ("input", "recordings_folders"),
        coerce_json_or_csv_list,
    ),
    _env_key(
        "TRANSCRIPTX_FILE_SELECTION_MODE",
        ("input", "file_selection_mode"),
        coerce_lower_strip,
        allowed_values=("prompt", "explore", "direct"),
        invalid_policy="warn_skip",
    ),
    _env_key("TRANSCRIPTX_OUTPUT_DIR", ("output", "base_output_dir"), coerce_str),
    _env_key("TRANSCRIPTX_LOG_LEVEL", ("logging", "level"), coerce_str),
    _env_key("TRANSCRIPTX_USE_EMOJIS", ("use_emojis",), coerce_bool_on_off),
    _env_key(
        "TRANSCRIPTX_AUDIO_PREPROCESSING_MODE",
        ("audio_preprocessing", "preprocessing_mode"),
        coerce_lower_strip,
        allowed_values=("selected", "auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_CONVERT_TO_MONO",
        ("audio_preprocessing", "convert_to_mono"),
        coerce_tri_state_bool_fallback,
        allowed_values=("auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_DOWNSAMPLE",
        ("audio_preprocessing", "downsample"),
        coerce_tri_state_bool_fallback,
        allowed_values=("auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE",
        ("audio_preprocessing", "target_sample_rate"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_NORMALIZE_MODE",
        ("audio_preprocessing", "normalize_mode"),
        coerce_lower_strip,
        allowed_values=("auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_TARGET_LUFS",
        ("audio_preprocessing", "target_lufs"),
        coerce_float,
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_DENOISE_MODE",
        ("audio_preprocessing", "denoise_mode"),
        coerce_lower_strip,
        allowed_values=("auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_DENOISE_STRENGTH",
        ("audio_preprocessing", "denoise_strength"),
        coerce_lower_strip,
        allowed_values=("low", "medium", "high"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_HIGHPASS_MODE",
        ("audio_preprocessing", "highpass_mode"),
        coerce_lower_strip,
        allowed_values=("auto", "suggest", "off"),
        invalid_policy="warn_skip",
    ),
    _env_key(
        "TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF",
        ("audio_preprocessing", "highpass_cutoff"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE",
        ("workflow", "speaker_gate", "threshold_value"),
        coerce_str,
        post_hook_target=("workflow", "speaker_gate"),
        post_hook_method="validate",
    ),
    _env_key(
        "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE",
        ("workflow", "speaker_gate", "threshold_type"),
        coerce_str,
        post_hook_target=("workflow", "speaker_gate"),
        post_hook_method="validate",
    ),
    _env_key(
        "TRANSCRIPTX_SPEAKER_GATE_MODE",
        ("workflow", "speaker_gate", "mode"),
        coerce_str,
        post_hook_target=("workflow", "speaker_gate"),
        post_hook_method="validate",
    ),
    _env_key(
        "TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT",
        ("workflow", "speaker_gate", "exemplar_count"),
        coerce_str,
        post_hook_target=("workflow", "speaker_gate"),
        post_hook_method="validate",
    ),
    _env_key("TRANSCRIPTX_LLM_ENABLED", ("llm", "enabled"), coerce_bool_on_off),
    _env_key(
        "TRANSCRIPTX_LLM_PROVIDER",
        ("llm", "provider"),
        coerce_lower_strip,
        allowed_values=("null", "ollama"),
        invalid_policy="warn_skip",
    ),
    _env_key("TRANSCRIPTX_LLM_MODEL", ("llm", "model"), coerce_str),
    _env_key("TRANSCRIPTX_LLM_BASE_URL", ("llm", "base_url"), coerce_str),
    _env_key("TRANSCRIPTX_LLM_SEED", ("llm", "seed"), coerce_int),
    _env_key(
        "TRANSCRIPTX_LLM_REQUEST_TIMEOUT",
        ("llm", "request_timeout"),
        coerce_float,
    ),
    _env_key(
        "TRANSCRIPTX_LLM_AVAILABILITY_TIMEOUT",
        ("llm", "availability_timeout"),
        coerce_float,
    ),
    _env_key(
        "TRANSCRIPTX_LLM_MAX_INPUT_CHARS",
        ("llm", "max_input_chars"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_LLM_MAX_OUTPUT_TOKENS",
        ("llm", "max_output_tokens"),
        coerce_int,
    ),
    _env_key(
        "TRANSCRIPTX_LLM_DEFAULT_TEMPERATURE",
        ("llm", "default_temperature"),
        coerce_float,
    ),
)

KNOWN_OVERRIDE_KEYS = frozenset(entry.env_name for entry in ENV_KEY_REGISTRY)


def _reject_legacy_audio_enabled_env() -> None:
    for name in LEGACY_REJECTED_KEYS:
        if os.getenv(name):
            raise ConfigLoadError(
                f"Environment variable {name} is no longer supported. "
                "Use TRANSCRIPTX_AUDIO_NORMALIZE_MODE, TRANSCRIPTX_AUDIO_DENOISE_MODE, "
                'or TRANSCRIPTX_AUDIO_HIGHPASS_MODE with values "auto", "suggest", or "off".',
                code="unsupported_legacy_shape",
            )


def _resolve_parent_and_leaf(
    root: Any, target_path: tuple[str, ...]
) -> tuple[Any | None, str | None]:
    if not target_path:
        return (None, None)
    if len(target_path) == 1:
        return (root, target_path[0])

    parent = root
    for segment in target_path[:-1]:
        if parent is None or not hasattr(parent, segment):
            return (None, None)
        parent = getattr(parent, segment)
    return (parent, target_path[-1])


def _resolve_object(root: Any, target_path: tuple[str, ...]) -> Any | None:
    current = root
    for segment in target_path:
        if current is None or not hasattr(current, segment):
            return None
        current = getattr(current, segment)
    return current


def _handle_invalid(env_key: EnvKey, raw_value: str, reason: str) -> None:
    if env_key.invalid_policy == "skip":
        return
    if env_key.invalid_policy == "warn_skip":
        log_warning(
            "CONFIG",
            (
                f"Skipping {env_key.env_name}: invalid value '{raw_value}' "
                f"({reason}); preserves mutation/error behavior and adds diagnostics."
            ),
        )
        return
    raise ConfigLoadError(
        f"Invalid value for {env_key.env_name}: '{raw_value}' ({reason})",
        code="invalid_value",
    )


def _scan_unknown_env_keys(*, strict: bool) -> None:
    for env_name in sorted(os.environ):
        if not env_name.startswith("TRANSCRIPTX_"):
            continue
        if env_name in KNOWN_OVERRIDE_KEYS:
            continue
        if env_name in INFRA_ENV_ALLOWLIST:
            continue
        if env_name in LEGACY_REJECTED_KEYS:
            continue

        message = (
            f"Unknown TRANSCRIPTX_* environment variable '{env_name}'. "
            "This key is not recognized by config env overrides."
        )
        if strict:
            raise ConfigLoadError(message, code="unsupported_key")
        log_warning("CONFIG", message)


def _is_strict_requested() -> bool:
    raw = os.getenv("TRANSCRIPTX_CONFIG_STRICT", "")
    return _normalize(raw) in TRUTHY_VALUES


def _apply_registry_to_config(
    config: Any,
    *,
    registry: tuple[EnvKey, ...],
    strict: bool | None = None,
) -> None:
    _reject_legacy_audio_enabled_env()

    effective_strict = _is_strict_requested() if strict is None else strict
    # Strict mode should fail closed before any mutation.
    _scan_unknown_env_keys(strict=effective_strict)

    pending_hooks: set[tuple[tuple[str, ...], str]] = set()

    for env_key in registry:
        raw = os.getenv(env_key.env_name)
        if raw is None:
            continue
        if not raw.strip():
            continue

        ok, coerced_value = env_key.coercer(raw)
        if not ok:
            _handle_invalid(env_key, raw, "coercion_failed")
            continue
        if (
            env_key.allowed_values is not None
            and coerced_value not in env_key.allowed_values
        ):
            _handle_invalid(env_key, raw, "outside_allowed_values")
            continue

        parent, leaf = _resolve_parent_and_leaf(config, env_key.target_path)
        if parent is None or leaf is None:
            continue
        if not hasattr(parent, leaf):
            continue

        setattr(parent, leaf, coerced_value)

        if env_key.post_hook_target and env_key.post_hook_method:
            pending_hooks.add((env_key.post_hook_target, env_key.post_hook_method))

    for target_path, method_name in pending_hooks:
        target_obj = _resolve_object(config, target_path)
        if target_obj is None or not hasattr(target_obj, method_name):
            continue
        getattr(target_obj, method_name)()


def apply_env_to_config(config: Any, *, strict: bool | None = None) -> None:
    """Apply canonical TRANSCRIPTX_* env overrides."""
    _apply_registry_to_config(config, registry=ENV_KEY_REGISTRY, strict=strict)
