"""Batch speaker auto-identification (voice + text mention + style)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from transcriptx.core.speaker_profiles.aggregates import list_profiles
from transcriptx.core.speaker_profiles.discovery import discover_occurrences_from_segments
from transcriptx.core.speaker_profiles.identify.apply import apply_decisions
from transcriptx.core.speaker_profiles.identify.artefact import write_identify_artefact
from transcriptx.core.speaker_profiles.identify.fusion import fuse_speaker_candidates
from transcriptx.core.speaker_profiles.identify.mentions import (
    attach_profile_ids,
    extract_mention_candidates,
)
from transcriptx.core.speaker_profiles.identify.models import (
    ChannelCandidate,
    IdentifyResult,
)
from transcriptx.core.speaker_profiles.identify.settings import (
    IdentifySettings,
    load_identify_settings,
)
from transcriptx.core.speaker_profiles.identify.style import (
    build_style_vector,
    collect_profile_style_refs,
    rank_style_open_set,
    texts_for_speaker,
)
from transcriptx.core.speaker_profiles.identify.voice_channel import (
    analyse_voice_candidates,
)
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    load_transcript_segments,
)
from transcriptx.core.speaker_profiles.voice.match_service import SpeakerMatchService
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService

logger = get_logger()


def _active_profile_names(root: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        for item in list_profiles(root=root):
            if item.status != "active":
                continue
            out.append((item.profile_id, item.display_name))
    except Exception:
        return []
    return out


class SpeakerIdentifyService:
    """Analyse unnamed speakers and optionally write names and/or profile links."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        resolver: ManagedTranscriptResolver | None = None,
        match_service: SpeakerMatchService | None = None,
        mapping: SpeakerMappingService | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else speaker_profiles_dir()
        self.resolver = resolver or ManagedTranscriptResolver()
        self.match_service = match_service
        self.mapping = mapping or SpeakerMappingService()

    def identify_transcript(
        self,
        transcript_path: Path | str,
        *,
        auto_name: bool,
        auto_link: bool,
        style_only_apply: bool | None = None,
        dry_run: bool = False,
        settings: IdentifySettings | None = None,
    ) -> IdentifyResult:
        path = Path(transcript_path)
        cfg = settings or load_identify_settings()
        style_only = (
            cfg.style_only_apply if style_only_apply is None else style_only_apply
        )
        mapping_state = self.mapping.get_mapping(str(path))
        ignored = set(mapping_state.ignored_speakers)

        try:
            segments = load_transcript_segments(path)
        except Exception as exc:
            return IdentifyResult(
                transcript_path=str(path),
                managed_transcript_id=None,
                auto_name=auto_name,
                auto_link=auto_link,
                dry_run=dry_run,
                decisions=(),
                applied=(),
                error=str(exc),
            )

        managed_id: str | None = None
        try:
            if self.resolver.is_managed_path(path):
                managed_id = self.resolver.resolve_path(path).managed_transcript_id
        except Exception:
            managed_id = None

        if managed_id:
            occurrences = discover_occurrences_from_segments(
                managed_transcript_id=managed_id,
                current_relpath=path.name,
                segments=segments,
            )
            speaker_ids = [occ.local_speaker_key for occ in occurrences]
        else:
            seen: list[str] = []
            for segment in segments:
                raw = segment.get("speaker_diarized_id") or segment.get("speaker")
                key = normalize_diarized_id(raw)
                if key and key not in seen:
                    seen.append(key)
            speaker_ids = seen

        eligible: list[str] = []
        skipped_named: list[str] = []
        for key in speaker_ids:
            if key in ignored:
                continue
            existing = mapping_state.speaker_map.get(key, "")
            if is_effective_speaker_name(key, existing):
                skipped_named.append(key)
                continue
            eligible.append(key)

        voice: dict[str, ChannelCandidate] = {}
        if managed_id:
            try:
                voice = analyse_voice_candidates(
                    managed_transcript_id=managed_id,
                    transcript_path=path,
                    segments=segments,
                    speaker_ids=eligible,
                    match_service=self.match_service,
                    root=self.root,
                )
            except Exception as exc:
                logger.info("Voice identify channel abstained: %s", exc)

        mentions = attach_profile_ids(
            extract_mention_candidates(segments),
            profiles=_active_profile_names(self.root),
        )
        mentions = {k: v for k, v in mentions.items() if k in set(eligible)}

        style: dict[str, ChannelCandidate] = {}
        try:
            refs, names = collect_profile_style_refs(
                root=self.root,
                exclude_managed_id=managed_id,
                resolver=self.resolver,
            )
            if refs:
                for key in eligible:
                    vector = build_style_vector(texts_for_speaker(segments, key))
                    if vector is None:
                        continue
                    ranked = rank_style_open_set(vector, refs, names=names)
                    if ranked is not None:
                        style[key] = ranked
        except Exception as exc:
            logger.info("Style identify channel abstained: %s", exc)

        decisions = fuse_speaker_candidates(
            speaker_ids=eligible,
            voice=voice,
            mentions=mentions,
            style=style,
            style_only_apply=style_only,
        )
        applied = apply_decisions(
            transcript_path=path,
            managed_transcript_id=managed_id,
            decisions=list(decisions),
            auto_name=auto_name,
            auto_link=auto_link,
            dry_run=dry_run,
            mapping=self.mapping,
            profiles_root=self.root,
        )
        named_count = sum(1 for row in applied if row.named)
        linked_count = sum(1 for row in applied if row.linked)
        skipped_count = sum(
            1 for row in applied if not row.named and not row.linked
        ) + len(skipped_named)
        result = IdentifyResult(
            transcript_path=str(path),
            managed_transcript_id=managed_id,
            auto_name=auto_name,
            auto_link=auto_link,
            dry_run=dry_run,
            decisions=tuple(decisions),
            applied=tuple(applied),
            named_count=named_count,
            linked_count=linked_count,
            skipped_count=skipped_count,
        )
        artefact = write_identify_artefact(result, root=self.root)
        return IdentifyResult(
            transcript_path=result.transcript_path,
            managed_transcript_id=result.managed_transcript_id,
            auto_name=result.auto_name,
            auto_link=result.auto_link,
            dry_run=result.dry_run,
            decisions=result.decisions,
            applied=result.applied,
            named_count=result.named_count,
            linked_count=result.linked_count,
            skipped_count=result.skipped_count,
            artefact_path=str(artefact) if artefact else None,
        )


def maybe_identify_admitted(
    transcript_path: Path | str,
    *,
    auto_name: bool | None = None,
    auto_link: bool | None = None,
    dry_run: bool = False,
) -> IdentifyResult | None:
    """Run identify using settings when either ingest knob is on."""
    settings = load_identify_settings()
    name = settings.auto_name if auto_name is None else auto_name
    link = settings.auto_link if auto_link is None else auto_link
    if not name and not link:
        return None
    return SpeakerIdentifyService().identify_transcript(
        transcript_path,
        auto_name=name,
        auto_link=link,
        dry_run=dry_run,
        settings=settings,
    )


def identify_many(
    paths: Sequence[Path | str],
    *,
    auto_name: bool,
    auto_link: bool,
    dry_run: bool = False,
    style_only_apply: bool | None = None,
) -> list[IdentifyResult]:
    service = SpeakerIdentifyService()
    results: list[IdentifyResult] = []
    for path in paths:
        try:
            results.append(
                service.identify_transcript(
                    path,
                    auto_name=auto_name,
                    auto_link=auto_link,
                    dry_run=dry_run,
                    style_only_apply=style_only_apply,
                )
            )
        except Exception as exc:
            results.append(
                IdentifyResult(
                    transcript_path=str(path),
                    managed_transcript_id=None,
                    auto_name=auto_name,
                    auto_link=auto_link,
                    dry_run=dry_run,
                    decisions=(),
                    applied=(),
                    error=str(exc),
                )
            )
    return results
