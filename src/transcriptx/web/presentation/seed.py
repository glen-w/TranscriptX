"""One-time seed of presentation mode for empty vs existing workspaces."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils import paths as paths_mod
from transcriptx.web.action_menus.prefs import INTERFACE_MENUS_FILENAME
from transcriptx.web.presentation.prefs import (
    MODE_FULL,
    MODE_GUIDED,
    PresentationDraft,
    PresentationMode,
    built_in_prefs,
    invalidate_presentation_cache,
    load_presentation_prefs,
    presentation_prefs_path,
    raw_file_revision,
    save_presentation_prefs,
)


def workspace_looks_existing(
    *,
    config_dir: Path | None = None,
    outputs_dir: Path | None = None,
) -> bool:
    """True when the workspace shows prior user/config footprint."""
    cfg = Path(config_dir or paths_mod.CONFIG_DIR)
    out = Path(outputs_dir or paths_mod.OUTPUTS_DIR)

    if (cfg / INTERFACE_MENUS_FILENAME).exists():
        return True
    if (cfg / "config.json").exists():
        return True

    index = out / ".transcriptx_index.json"
    if index.exists():
        try:
            import json

            payload = json.loads(index.read_text(encoding="utf-8"))
            transcripts = (
                payload.get("transcripts") if isinstance(payload, dict) else None
            )
            if isinstance(transcripts, dict) and transcripts:
                return True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # Unreadable index still implies a used workspace.
            return True

    if out.exists():
        for child in out.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_dir():
                return True
    return False


def seed_presentation_mode_if_needed(
    path: Path | None = None,
    *,
    config_dir: Path | None = None,
    outputs_dir: Path | None = None,
) -> PresentationMode:
    """Seed once: existing → Full controls; empty → Guided. Honour existing file."""
    target = path or presentation_prefs_path()
    if target.exists():
        prefs, draft = load_presentation_prefs(target)
        if not draft.recovery:
            invalidate_presentation_cache()
            return prefs.mode
        # Recovery: do not overwrite; expose guided runtime default.
        return MODE_GUIDED

    mode: PresentationMode = (
        MODE_FULL
        if workspace_looks_existing(config_dir=config_dir, outputs_dir=outputs_dir)
        else MODE_GUIDED
    )
    prefs = built_in_prefs(mode=mode)
    draft = PresentationDraft(
        prefs=prefs,
        raw_file_revision=raw_file_revision(b""),
        path=target,
    )
    result = save_presentation_prefs(draft, path=target)
    if not result.ok:
        # Soft-fail: still return intended seed mode for this session.
        return mode
    invalidate_presentation_cache()
    return mode
