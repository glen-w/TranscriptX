"""Root validator fail-closed contracts for cleanup."""

from __future__ import annotations


from transcriptx.web.services.run_cleanup.models import SubjectType
from transcriptx.web.services.run_cleanup.root_validator import OutputRootValidator


def test_missing_root_still_checks_protected_overlap(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    transcripts = data / "transcripts"
    transcripts.mkdir()
    # Outputs configured inside protected transcripts (missing path)
    outputs = transcripts / "nested_outputs"
    groups = tmp_path / "groups"
    roots, blocking = OutputRootValidator.validate(
        outputs,
        groups,
        {"transcripts": transcripts},
        project_root=tmp_path,
        data_dir=data,
        state_dir=tmp_path / "state",
    )
    assert blocking
    assert any(r.kind is SubjectType.transcript and r.exists is False for r in roots)


def test_group_nested_under_outputs_allowed(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    groups = outputs / "groups"
    groups.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "transcripts").mkdir()
    roots, blocking = OutputRootValidator.validate(
        outputs,
        groups,
        {"transcripts": data / "transcripts"},
        project_root=tmp_path,
        data_dir=data,
        state_dir=tmp_path / "state",
    )
    assert not blocking
    assert len(roots) == 2


def test_reverse_nesting_blocked(tmp_path):
    groups = tmp_path / "groups"
    groups.mkdir()
    outputs = groups / "outputs"
    outputs.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "transcripts").mkdir()
    _roots, blocking = OutputRootValidator.validate(
        outputs,
        groups,
        {"transcripts": data / "transcripts"},
        project_root=tmp_path,
        data_dir=data,
        state_dir=tmp_path / "state",
    )
    assert blocking


def test_symlink_root_blocked(tmp_path):
    real = tmp_path / "real_outputs"
    real.mkdir()
    outputs = tmp_path / "outputs_link"
    outputs.symlink_to(real)
    groups = tmp_path / "groups"
    groups.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "transcripts").mkdir()
    _roots, blocking = OutputRootValidator.validate(
        outputs,
        groups,
        {"transcripts": data / "transcripts"},
        project_root=tmp_path,
        data_dir=data,
        state_dir=tmp_path / "state",
    )
    assert blocking
