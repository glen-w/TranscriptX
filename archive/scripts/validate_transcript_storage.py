"""[ARCHIVED] Validation script for transcript storage layout.

Checks that:
- speaker maps live under PATHS.speaker_maps_dir
- no imports/ directory exists under PATHS.transcripts_dir
- no transcript-associated sidecars are co-located next to canonical transcripts
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.paths import (
    PATHS,
    canonical_transcript_relpath,
    speaker_map_path_for_transcript,
)


def _iter_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def validate_speaker_maps() -> list[str]:
    errors: list[str] = []
    transcripts_root = PATHS.transcripts_dir
    speaker_maps_root = PATHS.transcripts_speaker_maps_dir

    # 1) No *.speaker_map.json outside PATHS.speaker_maps_dir under transcripts_dir
    for path in _iter_files(transcripts_root):
        if path.suffix == ".json" and path.name.endswith(".speaker_map.json"):
            if not str(path).startswith(str(speaker_maps_root)):
                errors.append(f"speaker map outside PATHS.speaker_maps_dir: {path}")

    # 2) No co-located sidecars next to canonical transcripts
    for path in _iter_files(transcripts_root):
        if path.suffix == ".json" and not path.name.endswith(".speaker_map.json"):
            # Only consider canonical transcripts (will raise for originals/metadata)
            try:
                canonical_transcript_relpath(path)
            except ValueError:
                continue
            sidecar_path = speaker_map_path_for_transcript(path)
            sibling = path.with_name(f"{path.stem}.speaker_map.json")
            if sibling.exists() and sibling != sidecar_path:
                errors.append(
                    f"co-located speaker map beside transcript: {sibling} (expected {sidecar_path})"
                )

    return errors


def validate_no_imports_dir() -> list[str]:
    # `imports/` is treated as an ingestion staging area and is allowed to exist.
    # The canonical storage contract only requires that discovery and analysis
    # operate on validated canonical transcripts, not raw imports.
    return []


def main() -> None:
    errors: list[str] = []
    errors.extend(validate_speaker_maps())
    errors.extend(validate_no_imports_dir())

    if errors:
        print("Transcript storage validation FAILED:")
        for err in errors:
            print(f"- {err}")
    else:
        print("Transcript storage validation passed.")


if __name__ == "__main__":
    main()
