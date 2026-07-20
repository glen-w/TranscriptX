"""Filesystem layout under ``.chart_descriptions/``."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.schemas import (
    ACTIVE_FILENAME,
    ATTEMPT_FILENAME,
    COMMIT_FILENAME,
    GENERATIONS_DIRNAME,
    LOCK_FILENAME,
    ROOT_NAME,
)


def descriptions_root(run_root: Path) -> Path:
    return Path(run_root) / ROOT_NAME


def active_path(run_root: Path) -> Path:
    return descriptions_root(run_root) / ACTIVE_FILENAME


def attempt_path(run_root: Path) -> Path:
    return descriptions_root(run_root) / ATTEMPT_FILENAME


def generations_dir(run_root: Path) -> Path:
    return descriptions_root(run_root) / GENERATIONS_DIRNAME


def generation_dir(run_root: Path, generation_id: str) -> Path:
    return generations_dir(run_root) / generation_id


def commit_path(run_root: Path, generation_id: str) -> Path:
    return generation_dir(run_root, generation_id) / COMMIT_FILENAME


def lock_path(run_root: Path) -> Path:
    return descriptions_root(run_root) / LOCK_FILENAME


def description_rel(chart_key_digest: str) -> str:
    return f"descriptions/{chart_key_digest}.json"


def description_md_rel(chart_key_digest: str) -> str:
    return f"descriptions/{chart_key_digest}.md"
