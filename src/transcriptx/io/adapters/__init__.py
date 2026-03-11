"""
AdapterRegistry — owns detection, priority sorting, and confidence scoring.

Detection algorithm (single deterministic rule):
  1. Score all adapters whose supported_extensions matches path.suffix.
  2. Choose the adapter with the highest score.
  3. Ties break on lower priority value.
  4. If highest score < CONFIDENCE_THRESHOLD, treat as no match.
  5. If no specific adapter matches, score generic fallback adapters
     (priority >= GENERIC_PRIORITY).
  6. If still no match, raise UnsupportedFormatError.

Unknown extensions: if path.suffix matches no adapter's supported_extensions,
step 1 returns all non-generic specific adapters and all are scored.  This is
the only case where extension narrowing is bypassed.

force_adapter: if provided, look up by source_id and return directly.  Raise
UnsupportedFormatError immediately if unknown — do not fall back to detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.adapters.base import SourceAdapter, UnsupportedFormatError

logger = get_logger()

CONFIDENCE_THRESHOLD = 0.3
GENERIC_PRIORITY = 1000


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: List[SourceAdapter] = []

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters.append(adapter)

    # ------------------------------------------------------------------
    # Public detection API
    # ------------------------------------------------------------------

    def detect(
        self,
        path: Path,
        content: bytes,
        force_adapter: Optional[str] = None,
    ) -> SourceAdapter:
        """Return the best adapter for (path, content).

        Raises UnsupportedFormatError if none qualify.
        """
        if force_adapter is not None:
            adapter = self._get_by_id(force_adapter)
            if adapter is None:
                raise UnsupportedFormatError(
                    f"No adapter registered with source_id={force_adapter!r}. "
                    f"Available: {[a.source_id for a in self._adapters]}"
                )
            return adapter

        ext = path.suffix.lower()
        specific = [a for a in self._adapters if a.priority < GENERIC_PRIORITY]
        fallbacks = [a for a in self._adapters if a.priority >= GENERIC_PRIORITY]

        ext_candidates = [a for a in specific if ext in a.supported_extensions]
        if not ext_candidates:
            # Unknown extension — score all specific adapters (bypass narrowing)
            ext_candidates = specific

        winner, best_score = self._score_candidates(ext_candidates, path, content)
        if winner is not None and best_score >= CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Adapter selected: {winner.source_id!r} "
                f"(score={best_score:.2f}, path={path.name!r})"
            )
            return winner

        # No specific adapter matched — try generic fallbacks
        fb_winner, fb_score = self._score_candidates(fallbacks, path, content)
        if fb_winner is not None and fb_score >= CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Fallback adapter selected: {fb_winner.source_id!r} "
                f"(score={fb_score:.2f}, path={path.name!r})"
            )
            return fb_winner

        raise UnsupportedFormatError(
            f"No adapter could handle {path.name!r} "
            f"(extension={ext!r}, best_score={max(best_score, 0.0):.2f}). "
            f"Registered adapters: {[a.source_id for a in self._adapters]}"
        )

    def detect_all_scores(
        self, path: Path, content: bytes
    ) -> List[Tuple[SourceAdapter, float]]:
        """Return (adapter, score) for every registered adapter, sorted by priority."""
        snippet = content[:4096]
        results: List[Tuple[SourceAdapter, float]] = []
        for adapter in sorted(self._adapters, key=lambda a: a.priority):
            try:
                score = adapter.detect_confidence(path, snippet)
            except Exception as exc:
                logger.debug(
                    f"detect_confidence raised for {adapter.source_id!r}: {exc}"
                )
                score = 0.0
            results.append((adapter, score))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_candidates(
        self, candidates: List[SourceAdapter], path: Path, content: bytes
    ) -> Tuple[Optional[SourceAdapter], float]:
        snippet = content[:4096]
        best_score = -1.0
        winner: Optional[SourceAdapter] = None
        # Sort by priority ascending so equal-score ties break on lower priority
        for adapter in sorted(candidates, key=lambda a: a.priority):
            try:
                score = adapter.detect_confidence(path, snippet)
            except Exception as exc:
                logger.debug(
                    f"detect_confidence raised for {adapter.source_id!r}: {exc}"
                )
                score = 0.0
            if score > best_score:
                best_score = score
                winner = adapter
        return winner, best_score

    def _get_by_id(self, source_id: str) -> Optional[SourceAdapter]:
        for adapter in self._adapters:
            if adapter.source_id == source_id:
                return adapter
        return None


# ── Global registry instance ──────────────────────────────────────────────────

registry = AdapterRegistry()


def _register_builtin_adapters() -> None:
    from transcriptx.io.adapters.vtt_adapter import VTTAdapter
    from transcriptx.io.adapters.srt_adapter import SRTAdapter
    from transcriptx.io.adapters.whisperx_adapter import WhisperXAdapter
    from transcriptx.io.adapters.sembly_adapter import SemblyAdapter
    from transcriptx.io.adapters.otter_adapter import OtterAdapter
    from transcriptx.io.adapters.fireflies_adapter import FirefliesAdapter
    from transcriptx.io.adapters.rev_adapter import RevAdapter
    from transcriptx.io.adapters.zoom_adapter import ZoomAdapter
    from transcriptx.io.adapters.generic_diarised_text_adapter import GenericDiarisedTextAdapter

    registry.register(VTTAdapter())
    registry.register(SRTAdapter())
    registry.register(WhisperXAdapter())
    registry.register(SemblyAdapter())
    registry.register(OtterAdapter())
    registry.register(FirefliesAdapter())
    registry.register(RevAdapter())
    registry.register(ZoomAdapter())
    registry.register(GenericDiarisedTextAdapter())


_register_builtin_adapters()
