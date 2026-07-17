"""Shared fixtures and golden normalisation for run-cleanup characterisation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    RunCleanupService,
)

GOLDENS_DIR = Path(__file__).resolve().parent / "goldens"
UPDATE_GOLDENS = os.environ.get("UPDATE_CLEANUP_CHARACTERISATION_GOLDENS") == "1"

_ABS_PATH_RE = re.compile(r"(?:/[^\s\"']+)|(?:[A-Za-z]:\\[^\s\"']+)")


def mk_run(root: Path, slug: str, run_id: str, content: str = "x") -> Path:
    run = root / slug / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.txt").write_text(content, encoding="utf-8")
    return run


def make_service(tmp_path: Path, **kwargs: Any) -> RunCleanupService:
    out = kwargs.pop("outputs_dir", tmp_path / "outputs")
    out.mkdir(parents=True, exist_ok=True)
    groups = kwargs.pop("group_outputs_dir", out / "groups")
    groups.mkdir(parents=True, exist_ok=True)
    state = kwargs.pop("state_dir", tmp_path / "state")
    state.mkdir(parents=True, exist_ok=True)
    data = kwargs.pop("data_dir", tmp_path / "data")
    data.mkdir(parents=True, exist_ok=True)
    for name in ("transcripts", "recordings", "corrections", "groups"):
        (data / name).mkdir(exist_ok=True)
    (data / "transcripts" / "metadata").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(exist_ok=True)
    return RunCleanupService(
        outputs_dir=out,
        group_outputs_dir=groups,
        state_dir=state,
        project_root=tmp_path,
        data_dir=data,
        config_dir=tmp_path / "config",
        **kwargs,
    )


def auth_for(mode: CleanupMode, plan_id: str) -> CleanupAuthorization:
    phrase = (
        CONFIRM_DELETE_ALL if mode is CleanupMode.DELETE_ALL else CONFIRM_DELETE_OLD
    )
    return CleanupAuthorization(
        acknowledged=True,
        phrase=phrase,
        mode=mode,
        plan_id=plan_id,
    )


def _replace_roots(text: str, roots: dict[str, str]) -> str:
    # Longest paths first to avoid partial overlaps.
    for abs_path, token in sorted(roots.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(abs_path, token)
        text = text.replace(abs_path.replace("\\", "/"), token)
    return text


def normalise_path_text(text: str, roots: dict[str, str]) -> str:
    text = _replace_roots(text, roots)
    text = text.replace("\\", "/")
    # Residual absolute paths (should be rare after root substitution).
    text = _ABS_PATH_RE.sub("<abs>", text)
    return text


def to_plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if hasattr(obj, "value") and obj.__class__.__name__.endswith(
        ("Mode", "Status", "Type", "Classification")
    ):
        return getattr(obj, "value")
    return obj


def normalise_structure(
    obj: Any,
    *,
    roots: dict[str, str],
    frozen_ids: dict[str, str] | None = None,
) -> Any:
    """JSON-friendly structure with path tokens and frozen id substitutions."""
    frozen_ids = frozen_ids or {}
    plain = to_plain(obj)
    raw = json.dumps(plain, sort_keys=True, ensure_ascii=False, default=str)
    raw = normalise_path_text(raw, roots)
    for real, token in frozen_ids.items():
        if real:
            raw = raw.replace(real, token)
    return json.loads(raw)


def root_tokens(svc: RunCleanupService) -> dict[str, str]:
    return {
        str(svc.outputs_dir.resolve()): "<OUTPUTS>",
        str(svc.group_outputs_dir.resolve()): "<GROUP_OUTPUTS>",
        str(svc.state_dir.resolve()): "<STATE>",
        str(svc.project_root.resolve()): "<PROJECT>",
        str(svc.data_dir.resolve()): "<DATA>",
        str(svc.config_dir.resolve()): "<CONFIG>",
        str(svc.outputs_dir): "<OUTPUTS>",
        str(svc.group_outputs_dir): "<GROUP_OUTPUTS>",
        str(svc.state_dir): "<STATE>",
        str(svc.project_root): "<PROJECT>",
        str(svc.data_dir): "<DATA>",
        str(svc.config_dir): "<CONFIG>",
    }


def assert_golden(name: str, payload: Any) -> None:
    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDENS_DIR / name
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if UPDATE_GOLDENS or not path.exists():
        path.write_text(rendered, encoding="utf-8")
        if not UPDATE_GOLDENS:
            # First create still asserts round-trip of what we wrote.
            pass
    expected = path.read_text(encoding="utf-8")
    assert rendered == expected, f"golden mismatch for {name}"
