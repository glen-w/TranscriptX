"""Clear Streamlit session selections that resolve to removed cleanup targets."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from transcriptx.web.services.run_cleanup.models import (
    CleanupTargetResult,
    TargetStatus,
)
from transcriptx.web.state import (
    RUN_ID_KEY,
    SELECTED_RUN_DIR,
    SUBJECT_ID_KEY,
    SUBJECT_TYPE_KEY,
    apply_subject_context,
)

_VISIBLE_REMOVAL_STATUSES = frozenset(
    {
        TargetStatus.VISIBLE_REMOVED,
        TargetStatus.PHYSICAL_DELETED,
        TargetStatus.INTERRUPTED_STAGING,
        TargetStatus.STAGED_JOURNAL_INCOMPLETE,
        TargetStatus.STAGED_IDENTITY_UNVERIFIED,
        TargetStatus.PHYSICAL_DELETE_FAILED,
        TargetStatus.PHYSICAL_DELETE_REFUSED,
        TargetStatus.PHYSICAL_DELETE_PARTIAL,
    }
)


def _identity_matches_session(
    t: CleanupTargetResult,
    *,
    subject_type: str,
    subject_id: str,
    run_id: str,
) -> bool:
    """Match TargetIdentity fields available on the result + session selection."""
    if t.subject_type.value != subject_type:
        return False
    if t.subject_id != subject_id:
        return False
    if t.run_id != run_id:
        return False
    return True


def _path_matches_selection(t: CleanupTargetResult, selected: str) -> bool:
    if selected == t.canonical_path:
        return True
    if t.root_relative_path and (
        selected.endswith("/" + t.root_relative_path)
        or selected.endswith(t.root_relative_path)
    ):
        return True
    return False


def clear_session_selections_for_removed_runs(
    session_state: Mapping[str, Any] | Any,
    targets: Iterable[CleanupTargetResult],
) -> bool:
    """Clear subject/run selection when it matches a successfully removed target.

    Matches TargetIdentity: subject type/id, run_id, and canonical or
    root-relative path when ``selected_run_dir`` is set. Optional source
    ``filesystem_dev``/``filesystem_ino`` on the result are required to match
    when the session also stores those keys.

    Does not clear for lock/subject skips, stale, or pre-rename staging failure.
    Physical-delete failure after visible removal still clears the old selection.
    """
    removed = [t for t in targets if t.status in _VISIBLE_REMOVAL_STATUSES]
    if not removed:
        return False

    changed = False
    subject_type = session_state.get(SUBJECT_TYPE_KEY)
    subject_id = session_state.get(SUBJECT_ID_KEY)
    run_id = session_state.get(RUN_ID_KEY)
    session_dev = session_state.get("selected_run_dev")
    session_ino = session_state.get("selected_run_ino")

    if subject_type and subject_id and run_id:
        for t in removed:
            if not _identity_matches_session(
                t,
                subject_type=str(subject_type),
                subject_id=str(subject_id),
                run_id=str(run_id),
            ):
                continue
            if t.filesystem_dev is not None and session_dev is not None:
                if int(t.filesystem_dev) != int(session_dev):
                    continue
            if t.filesystem_ino is not None and session_ino is not None:
                if int(t.filesystem_ino) != int(session_ino):
                    continue
            apply_subject_context(
                session_state,  # type: ignore[arg-type]
                subject_type=None,
                subject_id=None,
                run_id=None,
            )
            changed = True
            break

    selected_run_dir = session_state.get(SELECTED_RUN_DIR)
    if selected_run_dir:
        sel = str(selected_run_dir)
        for t in removed:
            if not _path_matches_selection(t, sel):
                continue
            if t.filesystem_dev is not None and session_dev is not None:
                if int(t.filesystem_dev) != int(session_dev):
                    continue
            if t.filesystem_ino is not None and session_ino is not None:
                if int(t.filesystem_ino) != int(session_ino):
                    continue
            session_state[SELECTED_RUN_DIR] = None  # type: ignore[index]
            changed = True
            break

    return changed
