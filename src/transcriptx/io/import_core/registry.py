from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.import_core.contracts import (
    DetectionClass,
    DetectionInput,
    DetectionOutcome,
    ImportAdapter,
    ImportOutcome,
    RankedCandidate,
)
from transcriptx.io.import_core.detection import SelectionPolicy, class_rank, kind_rank
from transcriptx.io.import_core.errors import (
    AmbiguousImportError,
    UnsupportedImportError,
)

logger = get_logger()


@dataclass(frozen=True)
class SelectedAdapter:
    adapter: ImportAdapter
    outcome: DetectionOutcome
    ranked_candidates: Sequence[RankedCandidate]


class ImportAdapterRegistry:
    def __init__(self, selection_policy: Optional[SelectionPolicy] = None) -> None:
        self._adapters: List[ImportAdapter] = []
        self._selection_policy = selection_policy or SelectionPolicy()

    def register(self, adapter: ImportAdapter) -> None:
        self._adapters.append(adapter)

    def get_adapter(self, adapter_id: str) -> Optional[ImportAdapter]:
        for adapter in self._adapters:
            if adapter.adapter_id == adapter_id:
                return adapter
        return None

    def detect(
        self,
        path: Path,
        content: bytes,
        force_adapter: Optional[str] = None,
        content_type_hint: Optional[str] = None,
    ) -> SelectedAdapter:
        if force_adapter is not None:
            forced = self.get_adapter(force_adapter)
            if forced is None:
                raise UnsupportedImportError(
                    path=str(path),
                    outcome=ImportOutcome.UNKNOWN_INPUT,
                    candidates=[],
                )
            forced_outcome = DetectionOutcome(
                detection_class=DetectionClass.DEFINITIVE,
                score=1.0,
                signals=("forced_adapter",),
            )
            ranked = [
                RankedCandidate(
                    adapter_id=forced.adapter_id,
                    adapter_kind=forced.adapter_kind,
                    detection_class=forced_outcome.detection_class,
                    score=forced_outcome.score,
                    signals=forced_outcome.signals,
                    hard_rejects=forced_outcome.hard_rejects,
                )
            ]
            return SelectedAdapter(forced, forced_outcome, ranked)

        outcomes = self._probe_all(path, content, content_type_hint)
        ranked = self._rank_candidates(outcomes)
        if not ranked:
            raise UnsupportedImportError(
                path=str(path),
                outcome=self._unsupported_outcome([]),
                candidates=[],
            )

        top = ranked[0]
        if class_rank(top.detection_class) < class_rank(
            self._selection_policy.minimum_detection_class
        ):
            raise UnsupportedImportError(
                path=str(path),
                outcome=self._unsupported_outcome(ranked),
                candidates=ranked,
            )

        if len(ranked) > 1:
            second = ranked[1]
            same_kind = top.adapter_kind == second.adapter_kind
            same_class = top.detection_class == second.detection_class
            close = (
                abs(top.score - second.score)
                <= self._selection_policy.ambiguous_score_delta
            )
            if (
                same_kind
                and same_class
                and close
                and top.detection_class != DetectionClass.DEFINITIVE
            ):
                raise AmbiguousImportError(path=str(path), candidates=ranked[:3])

        selected = self.get_adapter(top.adapter_id)
        if selected is None:
            raise UnsupportedImportError(
                path=str(path),
                outcome=self._unsupported_outcome(ranked),
                candidates=ranked,
            )
        selected_outcome = outcomes[
            [a.adapter_id for a, _ in outcomes].index(top.adapter_id)
        ][1]
        return SelectedAdapter(
            adapter=selected,
            outcome=selected_outcome,
            ranked_candidates=ranked,
        )

    def _probe_all(
        self,
        path: Path,
        content: bytes,
        content_type_hint: Optional[str],
    ) -> List[tuple[ImportAdapter, DetectionOutcome]]:
        snippet = content[:4096]
        json_skeleton = _json_skeleton(snippet)
        ext = path.suffix.lower()

        by_ext = [a for a in self._adapters if ext in a.supported_extensions]
        generic = [a for a in self._adapters if a.adapter_kind.value == "generic"]
        candidates = by_ext or [a for a in self._adapters if a not in generic]
        if not candidates:
            candidates = list(self._adapters)

        results: List[tuple[ImportAdapter, DetectionOutcome]] = []
        for adapter in candidates:
            try:
                outcome = adapter.probe(
                    DetectionInput(
                        path=path,
                        extension=ext,
                        content_type_hint=content_type_hint,
                        snippet=snippet,
                        json_skeleton=json_skeleton,
                    )
                )
            except Exception as exc:
                logger.debug("Probe failed for %s: %s", adapter.adapter_id, exc)
                outcome = DetectionOutcome(
                    detection_class=DetectionClass.REJECT,
                    score=0.0,
                    hard_rejects=("probe_exception",),
                )
            results.append((adapter, outcome))
        return results

    def _rank_candidates(
        self,
        outcomes: Sequence[tuple[ImportAdapter, DetectionOutcome]],
    ) -> List[RankedCandidate]:
        ranked = [
            RankedCandidate(
                adapter_id=adapter.adapter_id,
                adapter_kind=adapter.adapter_kind,
                detection_class=outcome.detection_class,
                score=float(outcome.score),
                signals=tuple(outcome.signals),
                hard_rejects=tuple(outcome.hard_rejects),
            )
            for adapter, outcome in outcomes
            if outcome.detection_class != DetectionClass.REJECT
        ]
        ranked.sort(
            key=lambda c: (
                kind_rank(c.adapter_kind),
                class_rank(c.detection_class),
                c.score,
                -self._priority_for(c.adapter_id),
            ),
            reverse=True,
        )
        return ranked

    def _priority_for(self, adapter_id: str) -> int:
        adapter = self.get_adapter(adapter_id)
        return 0 if adapter is None else int(adapter.detection_priority)

    def _unsupported_outcome(self, ranked: Sequence[RankedCandidate]) -> ImportOutcome:
        if not ranked:
            return ImportOutcome.UNKNOWN_INPUT
        if any(c.detection_class == DetectionClass.POSSIBLE for c in ranked):
            return ImportOutcome.RECOGNIZED_FAMILY_UNSUPPORTED
        return ImportOutcome.UNKNOWN_INPUT


def _json_skeleton(snippet: bytes) -> Optional[dict]:
    try:
        data = json.loads(snippet.decode("utf-8", errors="replace"))
    except Exception:
        return None
    if isinstance(data, dict):
        # include keys only; avoid parsing cost/drift
        return {"keys": sorted(str(k) for k in data.keys())[:50]}
    if isinstance(data, list):
        return {"kind": "list", "length_hint": len(data)}
    return {"kind": type(data).__name__}
