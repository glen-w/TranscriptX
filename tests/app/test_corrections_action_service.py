"""Unit tests for Corrections revisioned command protocol."""

from __future__ import annotations

from transcriptx.app.corrections import (
    CorrectionsActionService,
    CorrectionsCommand,
    new_corrections_action_id,
)


class _Ctrl:
    def __init__(self) -> None:
        self.applied = 0
        self.decisions = []
        self._session_rev = "s1"
        self._cand_rev = "c1"

    def session_revision(self, _sid):
        return self._session_rev

    def candidate_revision(self, _sid, _cid):
        return self._cand_rev

    def record_decision(self, session_id, candidate_id, action, **payload):
        self.decisions.append((session_id, candidate_id, action, payload))

    def apply_and_export(self, session_id, **payload):
        self.applied += 1


def test_duplicate_action_id_does_not_apply_twice() -> None:
    ctrl = _Ctrl()
    svc = CorrectionsActionService(ctrl)
    aid = new_corrections_action_id()
    cmd = CorrectionsCommand(
        action="apply_export",
        session_id="sess",
        action_id=aid,
        action_seq=1,
        expected_session_revision="s1",
    )
    a1 = svc.execute(cmd)
    a2 = svc.execute(cmd)
    assert a1.apply_export_committed is True
    assert a2 is a1
    assert ctrl.applied == 1


def test_stale_candidate_revision_rejects() -> None:
    ctrl = _Ctrl()
    svc = CorrectionsActionService(ctrl)
    ack = svc.execute(
        CorrectionsCommand(
            action="accept",
            session_id="sess",
            action_id=new_corrections_action_id(),
            action_seq=2,
            expected_session_revision="s1",
            expected_candidate_revision="old",
            candidate_id="cand1",
        )
    )
    assert ack.status == "rejected_stale"
    assert ctrl.decisions == []
