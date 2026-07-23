"""Speaker-profiles backup / export inventory (excludes voice artefacts)."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.voice.export_exclude import (
    filter_speaker_profiles_export_paths,
    is_voice_excluded_relpath,
)


def iter_speaker_profiles_paths_for_backup(root: Path) -> list[Path]:
    """List durable speaker_profiles files eligible for ordinary backup/export.

    Excludes ``voice/`` and ``.cache/voice/`` (biometric-derived / disposable).
    Includes profiles, links, events, operations journals, and avatar assets.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if is_voice_excluded_relpath(rel):
            continue
        # Skip disposable aggregate cache (non-voice) unless explicitly wanted —
        # Phase 1 contract: .cache/ is disposable; omit from ordinary backup of
        # canonical state. Avatars under profiles/assets are included.
        if rel == ".cache" or rel.startswith(".cache/"):
            continue
        candidates.append(path)
    return filter_speaker_profiles_export_paths(root, candidates)
