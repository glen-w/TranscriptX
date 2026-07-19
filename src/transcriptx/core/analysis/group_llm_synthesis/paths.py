"""Path helpers for group LLM synthesis layout."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    ACTIVE_FILENAME,
    COMMIT_FILENAME,
    GENERATIONS_DIRNAME,
    LOCK_FILENAME,
    OUTCOME_FILENAME,
    SYNTHESIS_ROOT_NAME,
)

GLOBAL_COLLECT_REL = "llm_summary/llm_summary.json"
SPEAKER_ROWS_REL = "llm_speaker_summary/speaker_rows.json"


def synthesis_root(run_root: Path) -> Path:
    return Path(run_root) / SYNTHESIS_ROOT_NAME


def lock_path(run_root: Path) -> Path:
    return synthesis_root(run_root) / LOCK_FILENAME


def active_path(run_root: Path) -> Path:
    return synthesis_root(run_root) / ACTIVE_FILENAME


def generations_dir(run_root: Path) -> Path:
    return synthesis_root(run_root) / GENERATIONS_DIRNAME


def generation_dir(run_root: Path, generation_id: str) -> Path:
    return generations_dir(run_root) / generation_id


def commit_path(run_root: Path, generation_id: str) -> Path:
    return generation_dir(run_root, generation_id) / COMMIT_FILENAME


def outcome_path(run_root: Path, generation_id: str) -> Path:
    return generation_dir(run_root, generation_id) / OUTCOME_FILENAME


def global_summary_rel() -> str:
    return "llm_summary/group_llm_summary.json"


def global_summary_md_rel() -> str:
    return "llm_summary/group_llm_summary.md"


def speaker_index_rel() -> str:
    return "llm_speaker_summary/group_llm_speaker_summary_index.json"


def speaker_index_md_rel() -> str:
    return "llm_speaker_summary/group_llm_speaker_summary_index.md"


def speaker_artifact_rel(artifact_token: str, ext: str) -> str:
    return (
        "llm_speaker_summary/group_llm_speaker_summaries/"
        f"{artifact_token}_group_llm_speaker_summary.{ext}"
    )


def global_collect_path(run_root: Path) -> Path:
    return Path(run_root) / GLOBAL_COLLECT_REL


def speaker_rows_path(run_root: Path) -> Path:
    return Path(run_root) / SPEAKER_ROWS_REL
