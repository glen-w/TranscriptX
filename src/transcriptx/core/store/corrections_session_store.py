"""Atomic storage for transcript-scoped correction sessions (indexed layout + events)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import PATHS

logger = get_logger()
_CORRECTIONS_ROOT = PATHS.data_dir / "corrections"


def _maybe_migrate_repo_corrections_to_data_dir() -> None:
    """Move <repo>/.transcriptx/corrections → <data_dir>/corrections once in a source tree."""
    root = Path(PATHS.project_root)
    if not (root / "pyproject.toml").exists():
        return
    legacy = root / ".transcriptx" / "corrections"
    primary = PATHS.data_dir / "corrections"
    if not legacy.exists() or legacy.resolve() == primary.resolve():
        return
    if primary.exists():
        return
    try:
        import shutil

        shutil.move(str(legacy), str(primary))
        logger.info("Migrated corrections sessions from %s to %s", legacy, primary)
    except OSError as e:
        logger.warning("Could not migrate corrections sessions from %s: %s", legacy, e)


_maybe_migrate_repo_corrections_to_data_dir()


def corrections_root() -> Path:
    return _CORRECTIONS_ROOT


def sessions_layout_root() -> Path:
    return corrections_root() / "sessions"


def session_dir_for_transcript(transcript_path: str | Path) -> Path:
    return corrections_root() / Path(transcript_path).stem


def session_path_for_transcript(transcript_path: str | Path) -> Path:
    return session_dir_for_transcript(transcript_path) / "session.json"


def _shard(session_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]", "_", session_id)
    if len(safe) >= 2:
        return safe[:2].lower()
    return (safe + "00")[:2].lower() if safe else "00"


def session_dir_for_session_id(session_id: str) -> Path:
    return sessions_layout_root() / _shard(session_id) / session_id


def session_json_for_session_id(session_id: str) -> Path:
    return session_dir_for_session_id(session_id) / "session.json"


def events_path_for_session_id(session_id: str) -> Path:
    return session_dir_for_session_id(session_id) / "events.jsonl"


def index_path() -> Path:
    return sessions_layout_root() / "sessions_index.json"


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _atomic_append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        if not line.endswith("\n"):
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_index() -> Dict[str, Any]:
    return {"index_schema_version": 1, "entries": {}}


class CorrectionsSessionStore:
    """Single-writer storage: legacy stem dirs + indexed sessions/<shard>/<id>/ layout."""

    def _load_index(self) -> Dict[str, Any]:
        p = index_path()
        if not p.exists():
            return _default_index()
        try:
            with open(p, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return _default_index()
            if "entries" not in data:
                data["entries"] = {}
            return data
        except Exception:
            return _default_index()

    def _save_index(self, data: Dict[str, Any], *, timeout: int = 15) -> None:
        p = index_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(p, timeout=timeout):
            _atomic_write(p, dict(data))

    def _rel_path(self, session_id: str) -> str:
        return f"{_shard(session_id)}/{session_id}"

    def _update_index_entry(
        self,
        session_id: str,
        transcript_path: str,
        *,
        current_generation_id: Optional[int],
        timeout: int = 15,
    ) -> None:
        p = index_path()
        with FileLock(p, timeout=timeout):
            data = self._load_index()
            data.setdefault("entries", {})
            data["entries"][session_id] = {
                "rel_path": self._rel_path(session_id),
                "transcript_path": transcript_path,
                "updated_at": _now_iso(),
                "current_generation_id": current_generation_id,
            }
            _atomic_write(p, data)

    def read(self, transcript_path: str | Path) -> Optional[Dict[str, Any]]:
        normalized = str(Path(transcript_path).expanduser().resolve())
        npath = Path(normalized)

        idx = self._load_index()
        best_path: Optional[Path] = None
        best_ts = ""
        for ent in idx.get("entries", {}).values():
            tp = ent.get("transcript_path")
            if not tp:
                continue
            try:
                if Path(tp).resolve() == npath:
                    rel = ent.get("rel_path")
                    if rel:
                        sp = sessions_layout_root() / rel / "session.json"
                        if sp.exists():
                            ts = str(ent.get("updated_at") or "")
                            if ts >= best_ts:
                                best_ts = ts
                                best_path = sp
            except Exception:
                continue
        if best_path is not None:
            with open(best_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

        leg = session_path_for_transcript(normalized)
        if leg.exists():
            with open(leg, "r", encoding="utf-8") as handle:
                return json.load(handle)
        return None

    def write(
        self,
        transcript_path: str | Path,
        data: Dict[str, Any],
        *,
        reason: str = "write",
        timeout: int = 15,
        update_index: bool = True,
    ) -> None:
        transcript_path = str(Path(transcript_path).expanduser().resolve())
        sid = data.get("session_id")
        if not sid:
            raise ValueError("session data must include session_id")
        sdir = session_dir_for_session_id(str(sid))
        sdir.mkdir(parents=True, exist_ok=True)
        path = sdir / "session.json"
        lock_path = sdir / "session.dir.lock"
        payload = dict(data)
        gen_id = payload.get("current_generation_id")
        with FileLock(lock_path, timeout=timeout):
            _atomic_write(path, payload)
        if update_index:
            self._update_index_entry(
                str(sid),
                transcript_path,
                current_generation_id=gen_id if gen_id is not None else None,
                timeout=timeout,
            )
        leg = session_path_for_transcript(transcript_path)
        if leg.exists() and leg.resolve() != path.resolve():
            try:
                leg.unlink()
            except OSError:
                logger.warning("Could not remove legacy session file %s", leg)
        logger.debug("Wrote corrections session %s for reason=%s", path, reason)

    def mutate(
        self,
        transcript_path: str | Path,
        mutator: Callable[[Dict[str, Any]], None],
        *,
        reason: str = "mutate",
        timeout: int = 15,
    ) -> Dict[str, Any]:
        transcript_path = str(Path(transcript_path).expanduser().resolve())
        current = self.read(transcript_path)
        if not current:
            raise ValueError(f"No session for transcript {transcript_path}")
        mutator(current)
        self.write(transcript_path, current, reason=reason, timeout=timeout)
        return current

    def find_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        idx = self._load_index()
        ent = idx.get("entries", {}).get(session_id)
        if ent and ent.get("rel_path"):
            sp = sessions_layout_root() / ent["rel_path"] / "session.json"
            if sp.exists():
                try:
                    with open(sp, "r", encoding="utf-8") as handle:
                        return json.load(handle)
                except Exception:
                    pass

        sp = session_json_for_session_id(session_id)
        if sp.exists():
            try:
                with open(sp, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception:
                pass

        sl = sessions_layout_root()
        if sl.exists():
            for path in sl.rglob("session.json"):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                except Exception:
                    continue
                if isinstance(data, dict) and data.get("session_id") == session_id:
                    return data

        cr = corrections_root()
        if cr.exists():
            for path in cr.iterdir():
                if path.is_dir() and path.name != "sessions":
                    sj = path / "session.json"
                    if sj.exists():
                        try:
                            with open(sj, "r", encoding="utf-8") as handle:
                                data = json.load(handle)
                        except Exception:
                            continue
                        if (
                            isinstance(data, dict)
                            and data.get("session_id") == session_id
                        ):
                            return data
        return None

    def read_event_lines(self, session_id: str) -> List[str]:
        ep = events_path_for_session_id(session_id)
        if not ep.exists():
            return []
        with open(ep, "r", encoding="utf-8") as handle:
            return handle.readlines()

    def append_event_jsonl(
        self,
        session_id: str,
        event_obj: Dict[str, Any],
        *,
        timeout: int = 15,
    ) -> None:
        ep = events_path_for_session_id(session_id)
        lock_target = session_dir_for_session_id(session_id) / "session.dir.lock"
        line = json.dumps(event_obj, ensure_ascii=False, separators=(",", ":"))
        with FileLock(lock_target, timeout=timeout):
            _atomic_append_line(ep, line)

    def write_and_append_event(
        self,
        transcript_path: str | Path,
        session_dict: Dict[str, Any],
        event_obj: Dict[str, Any],
        *,
        timeout: int = 15,
    ) -> None:
        """Append one JSONL event then write session.json under the session dir lock."""
        transcript_path = str(Path(transcript_path).expanduser().resolve())
        sid = str(session_dict["session_id"])
        sdir = session_dir_for_session_id(sid)
        sdir.mkdir(parents=True, exist_ok=True)
        lock_path = sdir / "session.dir.lock"
        sj = sdir / "session.json"
        ej = sdir / "events.jsonl"
        line = json.dumps(event_obj, ensure_ascii=False, separators=(",", ":"))
        gen_id = session_dict.get("current_generation_id")
        with FileLock(lock_path, timeout=timeout):
            _atomic_append_line(ej, line)
            _atomic_write(sj, dict(session_dict))
        self._update_index_entry(
            sid,
            transcript_path,
            current_generation_id=gen_id if gen_id is not None else None,
            timeout=timeout,
        )
        leg = session_path_for_transcript(transcript_path)
        if leg.exists() and leg.resolve() != sj.resolve():
            try:
                leg.unlink()
            except OSError:
                logger.warning("Could not remove legacy session file %s", leg)
        logger.debug("Wrote session+event for %s", sid)

    def ensure_session(
        self, transcript_path: str | Path, *, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        transcript_path = str(Path(transcript_path).expanduser().resolve())
        existing = self.read(transcript_path)
        if existing:
            return existing
        session = {
            "studio_schema_version": 1,
            "session_id": session_id or f"session_{Path(transcript_path).stem}",
            "transcript_path": transcript_path,
            "recorded_transcript_identity_hash": "",
            "detector_version": "1",
            "status": "active",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "candidates": [],
            "review_records": [],
            "rules": {},
        }
        self.write(transcript_path, session, reason="create")
        return session


def rebuild_sessions_index_from_session_roots() -> Dict[str, Any]:
    """Recovery: scan sessions/*/*/session.json and rebuild sessions_index.json."""
    root = sessions_layout_root()
    entries: Dict[str, Any] = {}
    if not root.exists():
        idx = _default_index()
        _atomic_write(index_path(), idx)
        return idx
    for path in root.rglob("session.json"):
        if path.name != "session.json":
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        sid = data.get("session_id")
        if not sid:
            continue
        rel = path.parent.relative_to(root)
        entries[str(sid)] = {
            "rel_path": str(rel).replace("\\", "/"),
            "transcript_path": data.get("transcript_path", ""),
            "updated_at": data.get("updated_at", _now_iso()),
            "current_generation_id": data.get("current_generation_id"),
        }
    idx = {"index_schema_version": 1, "entries": entries}
    _atomic_write(index_path(), idx)
    return idx
