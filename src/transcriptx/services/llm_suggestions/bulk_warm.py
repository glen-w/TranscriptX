"""Library-wide warm for assistive rename and speaker-name LLM suggestion caches."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Sequence

from transcriptx.core.speaker_profiles.identify.suggestions.cache import (
    load_cached_suggestions,
)
from transcriptx.core.speaker_profiles.identify.suggestions.service import (
    fingerprint_segments,
    suggest_speaker_names,
)
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    load_transcript_segments,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.rename.suggestions.cache import load_cached_rename_suggestions
from transcriptx.core.utils.rename.suggestions.service import (
    build_rename_suggestions_cache_key,
    suggest_rename_stems,
)
from transcriptx.core.speaker_profiles.errors import ManagedTranscriptResolverError

ProgressCallback = Callable[[int, int, str], None]


class BulkWarmKind(str, Enum):
    SPEAKER_NAMES = "speaker_names"
    RENAME = "rename"


class BulkWarmTargetStatus(str, Enum):
    OK = "ok"
    SKIPPED_FRESH = "skipped_fresh"
    SKIPPED_CONFIG = "skipped_config"
    SKIPPED_UNMANAGED = "skipped_unmanaged"
    ERROR = "error"


@dataclass(frozen=True)
class BulkWarmTargetPreview:
    transcript_path: str
    transcript_label: str
    managed_transcript_id: str | None
    kind: BulkWarmKind
    actionable: bool
    skip_reason: str = ""


@dataclass(frozen=True)
class BulkWarmPreview:
    transcript_count: int
    actionable_count: int
    skipped_config_count: int
    targets: list[BulkWarmTargetPreview] = field(default_factory=list)


@dataclass(frozen=True)
class BulkWarmTargetResult:
    transcript_path: str
    transcript_label: str
    managed_transcript_id: str | None
    kind: BulkWarmKind
    status: BulkWarmTargetStatus
    message: str = ""


@dataclass(frozen=True)
class BulkWarmResult:
    targets: list[BulkWarmTargetResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkWarmTargetStatus.OK)

    @property
    def skipped_fresh_count(self) -> int:
        return sum(
            1 for t in self.targets if t.status is BulkWarmTargetStatus.SKIPPED_FRESH
        )

    @property
    def error_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkWarmTargetStatus.ERROR)


def _transcript_label(path: Path) -> str:
    return path.stem or path.name


def _rename_content_mode() -> str:
    input_cfg = get_config().input
    return str(getattr(input_cfg, "rename_content_suggestions", "off") or "off")


def _speaker_name_cache_fresh(
    *,
    managed_transcript_id: str,
    transcript_path: Path,
    segments: Sequence[dict],
) -> bool:
    fp = fingerprint_segments(segments)
    return (
        load_cached_suggestions(
            managed_transcript_id,
            transcript_fingerprint=fp,
        )
        is not None
    )


def _rename_cache_fresh(transcript_path: Path, segments: Sequence[dict]) -> bool:
    path = Path(transcript_path)
    config = get_config()
    input_cfg = config.input
    content_mode = str(getattr(input_cfg, "rename_content_suggestions", "off") or "off")
    if content_mode != "auto":
        return False
    pattern = str(
        getattr(input_cfg, "smart_rename_pattern", "{yymmdd}_{period}_{n}")
        or "{yymmdd}_{period}_{n}"
    )
    suggest_transcript = bool(getattr(input_cfg, "rename_suggest_transcript", True))
    suggest_llm = bool(getattr(input_cfg, "rename_suggest_llm", False))
    suggest_web = bool(getattr(input_cfg, "rename_suggest_web", False))
    effort = str(getattr(input_cfg, "rename_suggestions_effort", "low") or "low")
    fingerprint = fingerprint_segments(segments)
    llm_model_tag = "llm-off"
    if suggest_llm:
        try:
            from transcriptx.core.analysis.llm_support.model_selection import (
                resolve_module_llm_model,
            )
            from transcriptx.core.utils.rename.suggestions.service import (
                RENAME_SUGGESTIONS_CONSUMER_ID,
            )

            llm_model_tag = resolve_module_llm_model(
                config.llm, RENAME_SUGGESTIONS_CONSUMER_ID
            ).model
        except Exception:
            llm_model_tag = "llm-unresolved"
    cache_key = build_rename_suggestions_cache_key(
        fingerprint=fingerprint,
        content_mode=content_mode,
        suggest_transcript=suggest_transcript,
        suggest_llm=suggest_llm,
        suggest_web=suggest_web,
        effort=effort,
        pattern=pattern,
        llm_model_tag=llm_model_tag,
    )
    return (
        load_cached_rename_suggestions(
            cache_key=cache_key,
            transcript_fingerprint=fingerprint,
        )
        is not None
    )


class BulkLlmSuggestionsService:
    """Warm assistive LLM suggestion caches across the managed library."""

    def __init__(
        self,
        *,
        resolver: ManagedTranscriptResolver | None = None,
    ) -> None:
        self.resolver = resolver or ManagedTranscriptResolver()

    def _resolve_targets(
        self,
        paths: Sequence[Path] | None,
        *,
        kinds: Sequence[BulkWarmKind],
    ) -> list[tuple[Path, str | None]]:
        """Return (path, managed_transcript_id) pairs."""
        if paths:
            out: list[tuple[Path, str | None]] = []
            for raw in paths:
                path = Path(raw).expanduser()
                try:
                    resolved = self.resolver.resolve_path(path)
                    out.append((Path(resolved.transcript_path), resolved.managed_transcript_id))
                except ManagedTranscriptResolverError:
                    out.append((path, None))
            return out
        admitted = self.resolver.list_admitted()
        return [
            (Path(r.transcript_path), r.managed_transcript_id) for r in admitted
        ]

    def preview(
        self,
        *,
        kinds: Sequence[BulkWarmKind],
        paths: Sequence[Path] | None = None,
    ) -> BulkWarmPreview:
        targets: list[BulkWarmTargetPreview] = []
        skipped_config = 0
        pairs = self._resolve_targets(paths, kinds=kinds)
        rename_mode = _rename_content_mode()
        for path, managed_id in pairs:
            label = _transcript_label(path)
            for kind in kinds:
                if kind is BulkWarmKind.SPEAKER_NAMES:
                    if not managed_id:
                        targets.append(
                            BulkWarmTargetPreview(
                                transcript_path=str(path),
                                transcript_label=label,
                                managed_transcript_id=None,
                                kind=kind,
                                actionable=False,
                                skip_reason="not_managed",
                            )
                        )
                        continue
                    targets.append(
                        BulkWarmTargetPreview(
                            transcript_path=str(path),
                            transcript_label=label,
                            managed_transcript_id=managed_id,
                            kind=kind,
                            actionable=True,
                        )
                    )
                elif kind is BulkWarmKind.RENAME:
                    if rename_mode != "auto":
                        skipped_config += 1
                        targets.append(
                            BulkWarmTargetPreview(
                                transcript_path=str(path),
                                transcript_label=label,
                                managed_transcript_id=managed_id,
                                kind=kind,
                                actionable=False,
                                skip_reason="rename_content_suggestions_off",
                            )
                        )
                    else:
                        targets.append(
                            BulkWarmTargetPreview(
                                transcript_path=str(path),
                                transcript_label=label,
                                managed_transcript_id=managed_id,
                                kind=kind,
                                actionable=True,
                            )
                        )
        actionable = sum(1 for t in targets if t.actionable)
        return BulkWarmPreview(
            transcript_count=len(pairs),
            actionable_count=actionable,
            skipped_config_count=skipped_config,
            targets=targets,
        )

    def warm(
        self,
        *,
        kinds: Sequence[BulkWarmKind],
        paths: Sequence[Path] | None = None,
        force_refresh: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkWarmResult:
        preview = self.preview(kinds=kinds, paths=paths)
        actionable = [t for t in preview.targets if t.actionable]
        total = len(actionable)
        index = 0
        results: list[BulkWarmTargetResult] = []
        segments_cache: dict[str, list[dict]] = {}

        for target in preview.targets:
            if not target.actionable:
                status = BulkWarmTargetStatus.SKIPPED_CONFIG
                if target.skip_reason == "not_managed":
                    status = BulkWarmTargetStatus.SKIPPED_UNMANAGED
                results.append(
                    BulkWarmTargetResult(
                        transcript_path=target.transcript_path,
                        transcript_label=target.transcript_label,
                        managed_transcript_id=target.managed_transcript_id,
                        kind=target.kind,
                        status=status,
                        message=target.skip_reason or "skipped",
                    )
                )
                continue

            index += 1
            label = f"{target.transcript_label} ({target.kind.value})"
            if progress_callback is not None:
                progress_callback(index, total, label)

            path = Path(target.transcript_path)
            if dry_run:
                results.append(
                    BulkWarmTargetResult(
                        transcript_path=target.transcript_path,
                        transcript_label=target.transcript_label,
                        managed_transcript_id=target.managed_transcript_id,
                        kind=target.kind,
                        status=BulkWarmTargetStatus.OK,
                        message="dry-run",
                    )
                )
                continue

            try:
                if target.transcript_path not in segments_cache:
                    segments_cache[target.transcript_path] = load_transcript_segments(path)
                segments = segments_cache[target.transcript_path]

                if target.kind is BulkWarmKind.SPEAKER_NAMES:
                    assert target.managed_transcript_id
                    if not force_refresh and _speaker_name_cache_fresh(
                        managed_transcript_id=target.managed_transcript_id,
                        transcript_path=path,
                        segments=segments,
                    ):
                        results.append(
                            BulkWarmTargetResult(
                                transcript_path=target.transcript_path,
                                transcript_label=target.transcript_label,
                                managed_transcript_id=target.managed_transcript_id,
                                kind=target.kind,
                                status=BulkWarmTargetStatus.SKIPPED_FRESH,
                                message="cache hit",
                            )
                        )
                        continue
                    result = suggest_speaker_names(
                        path,
                        managed_transcript_id=target.managed_transcript_id,
                        force_refresh=force_refresh,
                    )
                    if result.error:
                        results.append(
                            BulkWarmTargetResult(
                                transcript_path=target.transcript_path,
                                transcript_label=target.transcript_label,
                                managed_transcript_id=target.managed_transcript_id,
                                kind=target.kind,
                                status=BulkWarmTargetStatus.ERROR,
                                message=result.error,
                            )
                        )
                    else:
                        results.append(
                            BulkWarmTargetResult(
                                transcript_path=target.transcript_path,
                                transcript_label=target.transcript_label,
                                managed_transcript_id=target.managed_transcript_id,
                                kind=target.kind,
                                status=BulkWarmTargetStatus.OK,
                                message=result.status_message or "warmed",
                            )
                        )
                else:
                    if not force_refresh and _rename_cache_fresh(path, segments):
                        results.append(
                            BulkWarmTargetResult(
                                transcript_path=target.transcript_path,
                                transcript_label=target.transcript_label,
                                managed_transcript_id=target.managed_transcript_id,
                                kind=target.kind,
                                status=BulkWarmTargetStatus.SKIPPED_FRESH,
                                message="cache hit",
                            )
                        )
                        continue
                    rename_result = suggest_rename_stems(path, force_refresh=force_refresh)
                    results.append(
                        BulkWarmTargetResult(
                            transcript_path=target.transcript_path,
                            transcript_label=target.transcript_label,
                            managed_transcript_id=target.managed_transcript_id,
                            kind=target.kind,
                            status=BulkWarmTargetStatus.OK,
                            message=rename_result.status or "warmed",
                        )
                    )
            except Exception as exc:
                results.append(
                    BulkWarmTargetResult(
                        transcript_path=target.transcript_path,
                        transcript_label=target.transcript_label,
                        managed_transcript_id=target.managed_transcript_id,
                        kind=target.kind,
                        status=BulkWarmTargetStatus.ERROR,
                        message=str(exc),
                    )
                )
        return BulkWarmResult(targets=results)

    def preview_speaker_names(
        self, *, paths: Sequence[Path] | None = None
    ) -> BulkWarmPreview:
        return self.preview(kinds=[BulkWarmKind.SPEAKER_NAMES], paths=paths)

    def preview_rename(self, *, paths: Sequence[Path] | None = None) -> BulkWarmPreview:
        return self.preview(kinds=[BulkWarmKind.RENAME], paths=paths)

    def warm_speaker_names(
        self,
        *,
        paths: Sequence[Path] | None = None,
        force_refresh: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkWarmResult:
        return self.warm(
            kinds=[BulkWarmKind.SPEAKER_NAMES],
            paths=paths,
            force_refresh=force_refresh,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )

    def warm_rename(
        self,
        *,
        paths: Sequence[Path] | None = None,
        force_refresh: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkWarmResult:
        return self.warm(
            kinds=[BulkWarmKind.RENAME],
            paths=paths,
            force_refresh=force_refresh,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )
