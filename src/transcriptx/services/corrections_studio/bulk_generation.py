"""Bulk generate / regenerate Corrections Studio candidates across transcripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from transcriptx.core.store.corrections_session_store import CorrectionsSessionStore
from transcriptx.services.corrections_studio.service import CorrectionService

CONFIRM_REGENERATE_ALL = "REGENERATE ALL"

ProgressCallback = Callable[[int, int, str], None]


class BulkGenerationMode(str, Enum):
    GENERATE_MISSING = "generate_missing"
    REGENERATE_ALL = "regenerate_all"


class BulkTargetStatus(str, Enum):
    GENERATED = "generated"
    SKIPPED = "skipped"
    ABORTED = "aborted"
    ERROR = "error"


@dataclass(frozen=True)
class BulkGenerationTargetPreview:
    path: str
    base_name: str
    has_candidates: bool
    candidate_count: int


@dataclass(frozen=True)
class BulkGenerationPreview:
    mode: BulkGenerationMode
    transcript_count: int
    with_candidates: int
    without_candidates: int
    actionable_count: int
    targets: List[BulkGenerationTargetPreview] = field(default_factory=list)


@dataclass(frozen=True)
class BulkGenerationTargetResult:
    path: str
    base_name: str
    status: BulkTargetStatus
    candidate_count: int = 0
    message: str = ""


@dataclass(frozen=True)
class BulkGenerationResult:
    mode: BulkGenerationMode
    targets: List[BulkGenerationTargetResult] = field(default_factory=list)

    @property
    def generated_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkTargetStatus.GENERATED)

    @property
    def skipped_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkTargetStatus.SKIPPED)

    @property
    def aborted_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkTargetStatus.ABORTED)

    @property
    def error_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkTargetStatus.ERROR)


def _raw_candidate_count(raw: Optional[dict]) -> int:
    """Count persisted candidates without requiring a fully valid session blob."""
    if not isinstance(raw, dict):
        return 0
    cands = raw.get("candidates")
    return len(cands) if isinstance(cands, list) else 0


class BulkCorrectionsGenerationService:
    """Library-wide candidate generation via CorrectionService APIs."""

    def __init__(
        self,
        service: Optional[CorrectionService] = None,
        store: Optional[CorrectionsSessionStore] = None,
    ) -> None:
        self._svc = service or CorrectionService()
        self._store = store or self._svc.repo

    def preview(self, mode: BulkGenerationMode) -> BulkGenerationPreview:
        summaries = self._svc.list_transcript_summaries_for_studio()
        targets: List[BulkGenerationTargetPreview] = []
        with_candidates = 0
        without_candidates = 0
        for summary in summaries:
            raw = self._store.read(summary.path)
            count = _raw_candidate_count(raw)
            has = count > 0
            if has:
                with_candidates += 1
            else:
                without_candidates += 1
            targets.append(
                BulkGenerationTargetPreview(
                    path=summary.path,
                    base_name=summary.base_name,
                    has_candidates=has,
                    candidate_count=count,
                )
            )
        actionable = (
            without_candidates
            if mode is BulkGenerationMode.GENERATE_MISSING
            else len(targets)
        )
        return BulkGenerationPreview(
            mode=mode,
            transcript_count=len(targets),
            with_candidates=with_candidates,
            without_candidates=without_candidates,
            actionable_count=actionable,
            targets=targets,
        )

    def execute(
        self,
        mode: BulkGenerationMode,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkGenerationResult:
        force = mode is BulkGenerationMode.REGENERATE_ALL
        preview = self.preview(mode)
        results: List[BulkGenerationTargetResult] = []
        total = preview.transcript_count
        for index, target in enumerate(preview.targets, start=1):
            if progress_callback is not None:
                progress_callback(index, total, target.base_name or target.path)
            if mode is BulkGenerationMode.GENERATE_MISSING and target.has_candidates:
                results.append(
                    BulkGenerationTargetResult(
                        path=target.path,
                        base_name=target.base_name,
                        status=BulkTargetStatus.SKIPPED,
                        candidate_count=target.candidate_count,
                        message="Already has candidates",
                    )
                )
                continue
            try:
                session = self._svc.start_or_resume_session(target.path)
                if not force and session.candidates:
                    results.append(
                        BulkGenerationTargetResult(
                            path=target.path,
                            base_name=target.base_name,
                            status=BulkTargetStatus.SKIPPED,
                            candidate_count=len(session.candidates),
                            message="Already has candidates",
                        )
                    )
                    continue
                gen = self._svc.generate_candidates(session.session_id, force=force)
                if gen.commit_aborted:
                    results.append(
                        BulkGenerationTargetResult(
                            path=target.path,
                            base_name=target.base_name,
                            status=BulkTargetStatus.ABORTED,
                            candidate_count=len(gen.candidates),
                            message=gen.abort_reason or "Commit aborted",
                        )
                    )
                    continue
                results.append(
                    BulkGenerationTargetResult(
                        path=target.path,
                        base_name=target.base_name,
                        status=BulkTargetStatus.GENERATED,
                        candidate_count=len(gen.candidates),
                    )
                )
            except Exception as exc:
                results.append(
                    BulkGenerationTargetResult(
                        path=target.path,
                        base_name=target.base_name,
                        status=BulkTargetStatus.ERROR,
                        message=str(exc),
                    )
                )
        return BulkGenerationResult(mode=mode, targets=results)
