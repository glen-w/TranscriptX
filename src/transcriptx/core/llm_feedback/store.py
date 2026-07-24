"""Locked O_APPEND JSONL store for LLM feedback events."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.llm_feedback.errors import (
    LlmFeedbackPathError,
    LlmFeedbackPersistenceError,
)
from transcriptx.core.llm_feedback.models import FeedbackEvent
from transcriptx.core.llm_feedback.path_safety import (
    assert_not_symlink,
    assert_path_under_root,
    assert_regular_file_or_absent,
    resolve_real,
)
from transcriptx.core.llm_feedback.validate import validate_event
from transcriptx.core.utils.file_lock import FileLock, LockAcquisitionError

_DIR_MODE = 0o700
_FILE_MODE = 0o600
_EVENTS_NAME = "events.jsonl"
_TOKENS_NAME = "submission_tokens.json"
_STORE_DIRNAME = "llm_feedback"


@dataclass(frozen=True)
class AppendResult:
    feedback_id: str
    duplicated: bool
    path: Path


@dataclass
class IterEventsResult:
    events: list[FeedbackEvent]
    tail_error: str | None = None


class FeedbackStore:
    """Append-only feedback store under ``{data_dir}/state/llm_feedback/``."""

    def __init__(self, data_dir: Path | str) -> None:
        self._data_dir = resolve_real(Path(data_dir))
        assert_not_symlink(Path(data_dir), what="data_dir")
        self._store_dir = self._data_dir / "state" / _STORE_DIRNAME
        self._events_path = self._store_dir / _EVENTS_NAME
        self._tokens_path = self._store_dir / _TOKENS_NAME
        self._lock_target = self._events_path

    @property
    def events_path(self) -> Path:
        return self._events_path

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    def _ensure_store_dir(self) -> None:
        state_dir = self._data_dir / "state"
        try:
            if state_dir.exists():
                assert_not_symlink(state_dir, what="state_dir")
            else:
                state_dir.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
                _chmod_best_effort(state_dir, _DIR_MODE)

            if self._store_dir.exists():
                assert_not_symlink(self._store_dir, what="llm_feedback dir")
                if not self._store_dir.is_dir():
                    raise LlmFeedbackPathError(
                        f"llm_feedback path is not a directory: {self._store_dir}"
                    )
            else:
                self._store_dir.mkdir(mode=_DIR_MODE, parents=False, exist_ok=True)
                _chmod_best_effort(self._store_dir, _DIR_MODE)

            assert_path_under_root(
                self._store_dir, self._data_dir, what="llm_feedback dir"
            )
            assert_path_under_root(
                self._events_path, self._data_dir, what="events.jsonl"
            )
            assert_path_under_root(
                self._tokens_path, self._data_dir, what="submission_tokens.json"
            )
            assert_regular_file_or_absent(self._events_path, what="events.jsonl")
            assert_regular_file_or_absent(
                self._tokens_path, what="submission_tokens.json"
            )
        except LlmFeedbackPathError:
            raise
        except OSError as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot prepare feedback store: {exc}"
            ) from exc

    def _load_tokens_unlocked(self) -> dict[str, str]:
        if not self._tokens_path.exists():
            return {}
        assert_not_symlink(self._tokens_path, what="submission_tokens.json")
        try:
            raw = self._tokens_path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot read submission token index: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise LlmFeedbackPersistenceError("submission_tokens.json must be an object")
        out: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                out[key] = value
        return out

    def _write_tokens_unlocked(self, tokens: dict[str, str]) -> None:
        payload = json.dumps(tokens, indent=2, ensure_ascii=False) + "\n"
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self._store_dir),
                prefix=".tokens_",
                suffix=".tmp",
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(tmp_path), str(self._tokens_path))
            _chmod_best_effort(self._tokens_path, _FILE_MODE)
            _fsync_dir(self._store_dir)
            tmp_path = None
        except OSError as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot write submission token index: {exc}"
            ) from exc
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def _append_line_unlocked(self, line: str) -> None:
        assert_regular_file_or_absent(self._events_path, what="events.jsonl")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        try:
            fd = os.open(str(self._events_path), flags, _FILE_MODE)
        except OSError as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot open events.jsonl for append: {exc}"
            ) from exc
        try:
            data = line.encode("utf-8")
            if not data.endswith(b"\n"):
                data += b"\n"
            written = 0
            while written < len(data):
                n = os.write(fd, data[written:])
                if n <= 0:
                    raise LlmFeedbackPersistenceError("short write to events.jsonl")
                written += n
            os.fsync(fd)
        except OSError as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot append to events.jsonl: {exc}"
            ) from exc
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        _chmod_best_effort(self._events_path, _FILE_MODE)
        _fsync_dir(self._store_dir)

    def append(self, event: FeedbackEvent | dict[str, Any]) -> AppendResult:
        validated = validate_event(event)
        self._ensure_store_dir()
        try:
            with FileLock(self._lock_target, timeout=30, blocking=True):
                tokens = self._load_tokens_unlocked()
                existing = tokens.get(validated.submission_token)
                if existing:
                    return AppendResult(
                        feedback_id=existing,
                        duplicated=True,
                        path=self._events_path,
                    )
                line = json.dumps(
                    validated.to_dict(),
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                self._append_line_unlocked(line)
                tokens[validated.submission_token] = validated.feedback_id
                self._write_tokens_unlocked(tokens)
                return AppendResult(
                    feedback_id=validated.feedback_id,
                    duplicated=False,
                    path=self._events_path,
                )
        except LockAcquisitionError as exc:
            raise LlmFeedbackPersistenceError(str(exc)) from exc

    def iter_events(self) -> IterEventsResult:
        self._ensure_store_dir()
        if not self._events_path.exists():
            return IterEventsResult(events=[], tail_error=None)
        assert_not_symlink(self._events_path, what="events.jsonl")
        try:
            text = self._events_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LlmFeedbackPersistenceError(
                f"cannot read events.jsonl: {exc}"
            ) from exc
        if not text:
            return IterEventsResult(events=[], tail_error=None)

        lines = text.split("\n")
        # Preserve trailing incomplete line without a terminating newline as tail.
        if text.endswith("\n"):
            body_lines = [ln for ln in lines if ln != ""]
            # split leaves a final "" after trailing newline — already dropped
            tail_candidate = None
        else:
            body_lines = lines[:-1]
            tail_candidate = lines[-1] if lines else None

        events: list[FeedbackEvent] = []
        tail_error: str | None = None

        for idx, line in enumerate(body_lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                events.append(validate_event(data))
            except (json.JSONDecodeError, LlmFeedbackPathError, Exception) as exc:
                # Malformed non-final lines are also reported; do not drop earlier.
                tail_error = f"malformed line {idx + 1}: {exc}"
                # Continue scanning remaining complete lines
                continue

        if tail_candidate is not None and tail_candidate.strip():
            try:
                data = json.loads(tail_candidate)
                events.append(validate_event(data))
            except Exception as exc:
                tail_error = f"malformed trailing line: {exc}"

        return IterEventsResult(events=events, tail_error=tail_error)

    def latest_feedback_id_for_instance(self, target_instance_id: str) -> str | None:
        result = self.iter_events()
        latest: FeedbackEvent | None = None
        for ev in result.events:
            if ev.target_instance_id != target_instance_id:
                continue
            if latest is None or ev.created_at >= latest.created_at:
                latest = ev
        return latest.feedback_id if latest else None


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
