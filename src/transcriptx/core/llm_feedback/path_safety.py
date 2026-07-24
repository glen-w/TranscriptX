"""Path safety for the LLM feedback store under data_dir."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from transcriptx.core.llm_feedback.errors import LlmFeedbackPathError


def resolve_real(path: Path) -> Path:
    return Path(path).expanduser().resolve()


def assert_not_symlink(path: Path, *, what: str = "path") -> Path:
    p = Path(path)
    if p.is_symlink():
        raise LlmFeedbackPathError(f"symlink rejected for {what}: {p}")
    return p


def assert_safe_artifact_relpath(relpath: str) -> str:
    if not isinstance(relpath, str) or not relpath.strip():
        raise LlmFeedbackPathError(
            "artifact_rel_path must be a non-empty relative path"
        )
    raw = relpath.strip().replace("\\", "/")
    if "\x00" in raw:
        raise LlmFeedbackPathError("artifact_rel_path must not contain NUL")
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise LlmFeedbackPathError(f"absolute path rejected: {raw!r}")
    if raw.startswith("//"):
        raise LlmFeedbackPathError(f"absolute path rejected: {raw!r}")
    pure = PurePosixPath(raw)
    if pure.is_absolute():
        raise LlmFeedbackPathError(f"absolute path rejected: {raw!r}")
    parts = pure.parts
    if not parts or parts == (".",):
        raise LlmFeedbackPathError(
            "artifact_rel_path must be a non-empty relative path"
        )
    for part in parts:
        if part in ("", ".", ".."):
            raise LlmFeedbackPathError(f"path traversal rejected: {raw!r}")
    return pure.as_posix()


def assert_path_under_root(path: Path, root: Path, *, what: str = "path") -> Path:
    root_resolved = resolve_real(root)
    assert_not_symlink(root, what=f"{what} root")
    resolved = resolve_real(path)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise LlmFeedbackPathError(
            f"{what} escapes allowed root: {resolved} not under {root_resolved}"
        ) from exc
    return resolved


def assert_regular_file_or_absent(path: Path, *, what: str = "file") -> None:
    assert_not_symlink(path, what=what)
    if path.exists() and not path.is_file():
        raise LlmFeedbackPathError(f"non-regular file rejected for {what}: {path}")
