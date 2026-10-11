"""Primary→secondary JSON generate with a run-scoped preferred-failure breaker."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Callable, Optional

from transcriptx.core.llm.llm_client import JsonResponseFormat, LLMClient
from transcriptx.core.llm.ollama_client import OllamaClient, build_ollama_client

logger = logging.getLogger(__name__)

ValidateFn = Callable[[str], bool]

_DEFAULT_THRESHOLD = 2


@dataclass
class _BreakerState:
    preferred_failures: int = 0
    threshold: int = _DEFAULT_THRESHOLD
    tripped: bool = False
    preferred_model: str = ""
    fallback_model: str = ""


_breaker: ContextVar[_BreakerState | None] = ContextVar(
    "transcriptx_llm_json_fallback_breaker", default=None
)
_last_outcome: ContextVar["JsonGenerateOutcome | None"] = ContextVar(
    "transcriptx_llm_json_last_outcome", default=None
)


@dataclass(frozen=True)
class JsonGenerateOutcome:
    """Result of a JSON generate that may have used the secondary model."""

    text: str
    model: str
    used_fallback: bool
    preferred_failed: bool
    detail: str = ""


def begin_json_fallback_scope(
    *,
    preferred_model: str | None = None,
    fallback_model: str | None = None,
    threshold: int | None = None,
) -> Token:
    """Start a run-scoped preferred-failure counter (warm / analysis entry)."""
    state = _BreakerState(
        preferred_failures=0,
        threshold=max(1, int(threshold if threshold is not None else _DEFAULT_THRESHOLD)),
        tripped=False,
        preferred_model=(preferred_model or "").strip(),
        fallback_model=(fallback_model or "").strip(),
    )
    return _breaker.set(state)


def end_json_fallback_scope(token: Token) -> None:
    _breaker.reset(token)


def reset_json_fallback_scope() -> None:
    """Clear breaker state (tests)."""
    _breaker.set(None)
    _last_outcome.set(None)


def get_last_json_generate_outcome() -> JsonGenerateOutcome | None:
    return _last_outcome.get()


def _record_outcome(outcome: JsonGenerateOutcome) -> None:
    _last_outcome.set(outcome)


def _note_preferred_failure() -> None:
    state = _breaker.get()
    if state is None:
        return
    state.preferred_failures += 1
    if state.preferred_failures >= state.threshold and not state.tripped:
        state.tripped = True
        logger.warning(
            "LLM preferred model JSON failures reached threshold %s "
            "(%s → sticking to secondary `%s` for this run)",
            state.threshold,
            f"`{state.preferred_model}` " if state.preferred_model else "",
            state.fallback_model or "(none)",
        )


def preferred_json_breaker_tripped() -> bool:
    state = _breaker.get()
    return bool(state and state.tripped)


def default_json_usable(text: str) -> bool:
    """True when ``text`` is non-empty JSON (object or array)."""
    raw = (text or "").strip()
    if not raw:
        return False
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(parsed, (dict, list))


class JsonFallbackLLMClient(LLMClient):
    """Wrap a primary Ollama client; on unusable JSON, try secondary once."""

    def __init__(
        self,
        primary: OllamaClient,
        secondary: OllamaClient | None,
        *,
        validate: ValidateFn | None = None,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._validate = validate or default_json_usable

    @property
    def model(self) -> str:
        """Last producing model when known; otherwise the primary tag."""
        last = _last_outcome.get()
        if last is not None:
            return last.model
        return self._primary.model

    @property
    def primary_model(self) -> str:
        return self._primary.model

    @property
    def secondary_model(self) -> str | None:
        return self._secondary.model if self._secondary is not None else None

    @property
    def base_url(self) -> str:
        return self._primary.base_url

    def is_available(self) -> bool:
        return self._primary.is_available()

    def generate(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Optional[JsonResponseFormat] = None,
        think: bool | str | None = None,
    ) -> str:
        if response_format is None:
            text = self._primary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=None,
                think=think,
            )
            _record_outcome(
                JsonGenerateOutcome(
                    text=text,
                    model=self._primary.model,
                    used_fallback=False,
                    preferred_failed=False,
                )
            )
            return text

        use_secondary_only = preferred_json_breaker_tripped()
        secondary = self._secondary
        can_fallback = (
            secondary is not None
            and secondary.model.strip()
            and secondary.model.strip() != self._primary.model.strip()
        )

        if use_secondary_only and can_fallback:
            assert secondary is not None
            text = secondary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                think=think,
            )
            _record_outcome(
                JsonGenerateOutcome(
                    text=text,
                    model=secondary.model,
                    used_fallback=True,
                    preferred_failed=True,
                    detail="preferred breaker tripped",
                )
            )
            return text

        preferred_error: Exception | None = None
        preferred_text: str | None = None
        try:
            preferred_text = self._primary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                think=think,
            )
        except Exception as exc:
            preferred_error = exc
            preferred_text = None

        if preferred_text is not None and self._validate(preferred_text):
            _record_outcome(
                JsonGenerateOutcome(
                    text=preferred_text,
                    model=self._primary.model,
                    used_fallback=False,
                    preferred_failed=False,
                )
            )
            return preferred_text

        _note_preferred_failure()
        detail = (
            str(preferred_error)
            if preferred_error is not None
            else "preferred JSON unusable"
        )
        if not can_fallback:
            if preferred_error is not None:
                raise preferred_error
            _record_outcome(
                JsonGenerateOutcome(
                    text=preferred_text or "",
                    model=self._primary.model,
                    used_fallback=False,
                    preferred_failed=True,
                    detail=detail,
                )
            )
            return preferred_text or ""

        assert secondary is not None
        logger.info(
            "LLM JSON preferred `%s` failed (%s); trying secondary `%s`",
            self._primary.model,
            detail,
            secondary.model,
        )
        try:
            text = secondary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                think=think,
            )
        except Exception:
            if preferred_error is not None:
                raise preferred_error
            raise
        _record_outcome(
            JsonGenerateOutcome(
                text=text,
                model=secondary.model,
                used_fallback=True,
                preferred_failed=True,
                detail=detail,
            )
        )
        return text


def wrap_client_with_json_fallback(
    primary: OllamaClient,
    *,
    llm_cfg: Any,
    request_timeout: float | None = None,
    availability_timeout: float | None = None,
    max_output_tokens: int | None = None,
    validate: ValidateFn | None = None,
) -> LLMClient:
    """Attach secondary model when ``llm.fallback_model`` is set and distinct.

    Run-scoped breaker counters are owned by ``begin_json_fallback_scope``
    (warm / analysis entrypoints). Without a scope, each call still falls back
    once but does not trip a run-wide breaker.
    """
    fallback = getattr(llm_cfg, "fallback_model", None)
    tag = (str(fallback).strip() if fallback else "") or ""
    if not tag or tag == primary.model.strip():
        return primary
    secondary = build_ollama_client(
        base_url=primary.base_url,
        model=tag,
        seed=int(getattr(llm_cfg, "seed", 42)),
        request_timeout=float(
            request_timeout
            if request_timeout is not None
            else getattr(llm_cfg, "request_timeout", 1350.0)
        ),
        availability_timeout=float(
            availability_timeout
            if availability_timeout is not None
            else getattr(llm_cfg, "availability_timeout", 7.5)
        ),
        max_output_tokens=(
            max_output_tokens
            if max_output_tokens is not None
            else getattr(llm_cfg, "max_output_tokens", None)
        ),
        effort=getattr(primary, "_effort", None),
    )
    state = _breaker.get()
    if state is not None:
        if not state.preferred_model:
            state.preferred_model = primary.model
        if not state.fallback_model:
            state.fallback_model = tag
        raw_thr = getattr(llm_cfg, "preferred_failure_threshold", state.threshold)
        try:
            state.threshold = max(1, int(raw_thr))
        except (TypeError, ValueError):
            pass
    return JsonFallbackLLMClient(primary, secondary, validate=validate)
