"""Virtual transcript paths for group-run OutputService instances."""

from __future__ import annotations

from pathlib import Path


def build_group_virtual_transcript_path(group_run_root: Path, agg_id: str) -> str:
    """
    Stable virtual path under the group run root for create_output_service.

    Avoids scattering ad-hoc .virtual strings across generators.
    """
    return str((group_run_root / f"{agg_id}.group.virtual").resolve())
