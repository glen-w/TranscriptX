"""Path safety for the LLM feedback store under data_dir."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.llm_feedback.errors import LlmFeedbackPathError
from transcriptx.core.utils import path_safety as _core


def resolve_real(path: Path) -> Path:
    return _core.resolve_real(path)


def assert_not_symlink(path: Path, *, what: str = "path") -> Path:
    return _core.assert_not_symlink(path, what=what, error_cls=LlmFeedbackPathError)


def assert_safe_artifact_relpath(relpath: str) -> str:
    return _core.assert_safe_relpath(
        relpath, what="artifact_rel_path", error_cls=LlmFeedbackPathError
    )


def assert_path_under_root(path: Path, root: Path, *, what: str = "path") -> Path:
    _core.assert_not_symlink(root, what=f"{what} root", error_cls=LlmFeedbackPathError)
    return _core.assert_path_under_root(
        path,
        root,
        what=what,
        error_cls=LlmFeedbackPathError,
        reject_symlink_root=False,
    )


def assert_regular_file_or_absent(path: Path, *, what: str = "file") -> None:
    assert_not_symlink(path, what=what)
    if path.exists() and not path.is_file():
        raise LlmFeedbackPathError(f"non-regular file rejected for {what}: {path}")
