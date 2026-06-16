from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.web.transcript_viewer.preflight import resolve_viewer_preflight


@dataclass
class _Subject:
    subject_type: str
    scope: str = "transcript"
    subject_id: str | None = "slug"
    members: list | None = None


def test_preflight_status_matrix() -> None:
    base_state = {"run_id": "run1"}

    def _run(subject, run_id="run1"):
        state = dict(base_state)
        if run_id is None:
            state.pop("run_id", None)
        else:
            state["run_id"] = run_id
        return resolve_viewer_preflight(
            state,
            resolve_subject=lambda _s: subject,
            get_run_root=lambda _scope, _run_id, _subject_id: Path("/tmp/run"),
        )

    assert _run(None).status == "no_subject"
    assert _run(_Subject("group", members=[])).status == "group_browser"
    assert _run(_Subject("other")).status == "wrong_subject"
    assert _run(_Subject("transcript"), run_id=None).status == "no_run"
    ok = _run(_Subject("transcript", scope="project", subject_id="foo"))
    assert ok.status == "ok"
    assert ok.context_result is not None
    assert ok.context_result.selected_session == "foo/run1"
    assert ok.context_result.run_root == Path("/tmp/run")
