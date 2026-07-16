"""Offline unit tests for corrections workflow branch coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.corrections.models import (
    Candidate,
    CorrectionConditions,
    CorrectionMemory,
    CorrectionRule,
    Decision,
    Occurrence,
)
from transcriptx.core.corrections import workflow as wf


def _candidate(
    wrong: str = "foo",
    right: str = "Foo",
    kind: str = "acronym",
    conf: float = 0.8,
    rule_id: str | None = None,
    occs: list[Occurrence] | None = None,
) -> Candidate:
    return Candidate(
        proposed_wrong=wrong,
        proposed_right=right,
        kind=kind,  # type: ignore[arg-type]
        confidence=conf,
        rule_id=rule_id,
        occurrences=occs
        or [
            Occurrence(
                segment_id="s1",
                snippet=wrong,
                span=(0, len(wrong)),
                speaker="Alice",
                time_start=0.0,
                time_end=1.0,
            )
        ],
    )


@pytest.mark.unit
def test_rule_signature_and_dedupe_merges() -> None:
    rule = CorrectionRule(
        type="token",
        wrong=["foo"],
        right="Foo",
        scope="project",
        conditions=CorrectionConditions(speaker="Alice", min_token_len=2),
    )
    sig = wf._rule_signature_for_dedupe(rule)
    assert sig[1] == "Alice"
    assert wf._rule_signature_for_dedupe(None) == (None, None)

    c1 = _candidate(conf=0.5, rule_id=rule.id)
    c2 = _candidate(conf=0.9, rule_id=rule.id)
    c2.occurrences = [
        Occurrence(segment_id="s1", snippet="foo", span=(0, 3)),
        Occurrence(segment_id="s2", snippet="foo", span=(1, 4)),
    ]
    merged = wf.dedupe_candidates([c1, c2], rules_by_id={rule.id: rule})
    assert len(merged) == 1
    assert merged[0].confidence == 0.9
    assert len(merged[0].occurrences) == 2
    assert wf._dedupe_candidates([c1]) == wf.dedupe_candidates([c1])


@pytest.mark.unit
def test_backup_and_write_updated_transcript(tmp_path) -> None:
    from pathlib import Path

    path = tmp_path / "t.json"
    path.write_text('{"segments": [{"text": "old"}]}')
    backup = wf._backup_transcript_file(str(path))
    assert Path(backup).exists()

    with (
        patch(
            "transcriptx.core.corrections.workflow.load_transcript",
            return_value={"segments": [{"text": "old"}]},
        ),
        patch("transcriptx.core.corrections.workflow.TranscriptStore") as store_cls,
    ):
        store = store_cls.return_value
        out = wf._write_updated_transcript(
            str(path), [{"text": "new"}], create_backup=False
        )
        assert out == str(path)
        store.write.assert_called_once()

    # list transcript → save_json path
    with (
        patch(
            "transcriptx.core.corrections.workflow.load_transcript",
            return_value=[{"text": "old"}],
        ),
        patch("transcriptx.core.corrections.workflow.save_json") as save_json,
    ):
        wf._write_updated_transcript(str(path), [{"text": "new2"}], create_backup=False)
        save_json.assert_called_once()


@pytest.mark.unit
def test_write_corrected_transcript_none_and_paths(tmp_path) -> None:
    assert wf.write_corrected_transcript(
        transcript_path="x", updated_segments=None
    ) is None
    assert (
        wf.write_corrected_transcript(transcript_path="x", updated_segments=[]) is None
    )

    path = tmp_path / "t.json"
    path.write_text('{"segments": []}')
    with (
        patch(
            "transcriptx.core.corrections.workflow.load_transcript",
            return_value={"segments": []},
        ),
        patch("transcriptx.core.corrections.workflow.TranscriptStore") as store_cls,
        patch(
            "transcriptx.core.corrections.workflow._backup_transcript_file",
            return_value=str(tmp_path / "bak"),
        ),
    ):
        bak = wf.write_corrected_transcript(
            transcript_path=str(path),
            updated_segments=[{"text": "z"}],
            create_backup=True,
        )
        assert bak == str(tmp_path / "bak")
        store_cls.return_value.write.assert_called_once()


@pytest.mark.unit
def test_run_corrections_on_segments_disabled() -> None:
    cfg = SimpleNamespace(analysis=SimpleNamespace(corrections=None))
    out = wf.run_corrections_on_segments(
        segments=[{"text": "a"}],
        transcript_path="/tmp/t.json",
        config=cfg,
    )
    assert out["status"] == "skipped"

    cfg2 = SimpleNamespace(
        analysis=SimpleNamespace(corrections=SimpleNamespace(enabled=False))
    )
    out2 = wf.run_corrections_on_segments(
        segments=[{"text": "a"}],
        transcript_path="/tmp/t.json",
        config=cfg2,
    )
    assert out2["status"] == "skipped"


def _corrections_config(**overrides):
    base = SimpleNamespace(
        enabled=True,
        interactive_review=False,
        known_acronyms=[],
        known_org_phrases={},
        consistency_similarity_threshold=0.88,
        fuzzy_similarity_threshold=0.85,
        enable_fuzzy=False,
        default_rule_scope="project",
        store_corrected_transcript=True,
        write_csv_summary=True,
        update_original_file=False,
        create_backup=True,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.mark.unit
def test_run_corrections_on_segments_auto_apply_and_artifacts(tmp_path, monkeypatch):
    rule = CorrectionRule(
        type="token",
        wrong=["foo"],
        right="Foo",
        scope="project",
        auto_apply=True,
        confidence=0.9,
    )
    cand = _candidate(rule_id=rule.id, conf=0.9)

    memory = CorrectionMemory(rules={rule.id: rule})
    fake_out = MagicMock()
    fake_out.base_name = "sample"
    fake_out.get_output_structure.return_value = SimpleNamespace(
        global_data_dir=tmp_path
    )
    fake_out.save_data = MagicMock(
        side_effect=lambda payload, name, format_type="json": str(tmp_path / f"{name}.{format_type}")
    )
    fake_out.get_artifacts.return_value = []

    cfg = SimpleNamespace(analysis=SimpleNamespace(corrections=_corrections_config()))

    monkeypatch.setattr(wf, "create_output_service", lambda *a, **k: fake_out)
    monkeypatch.setattr(wf, "load_memory", lambda **k: memory)
    monkeypatch.setattr(wf, "detect_memory_hits", lambda *a, **k: [cand])
    monkeypatch.setattr(wf, "detect_acronym_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_consistency_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_fuzzy_candidates", lambda *a, **k: [])
    monkeypatch.setattr(
        wf,
        "apply_corrections",
        lambda **k: (
            [{"text": "Foo"}],
            [{"rule_id": rule.id, "status": "applied"}],
        ),
    )
    monkeypatch.setattr(wf, "compute_transcript_identity_hash", lambda s: "key")
    monkeypatch.setattr(wf, "_derive_speaker_map", lambda *a, **k: {0: "Alice"})

    result = wf.run_corrections_on_segments(
        segments=[{"text": "foo", "speaker": "Alice"}],
        transcript_path=str(tmp_path / "t.json"),
        config=cfg,
        apply_changes=True,
    )
    assert result["status"] == "success"
    assert result["applied_count"] == 1
    assert result["corrected_transcript_path"]
    assert any(
        c.args[1] == "corrections_summary"
        for c in fake_out.save_data.call_args_list
    )


@pytest.mark.unit
def test_run_corrections_on_segments_external_decisions(tmp_path, monkeypatch):
    rule = CorrectionRule(
        type="token", wrong=["foo"], right="Foo", scope="project", confidence=0.5
    )
    cand = _candidate(rule_id=rule.id)
    memory = CorrectionMemory(rules={rule.id: rule})
    fake_out = MagicMock()
    fake_out.base_name = "sample"
    fake_out.get_output_structure.return_value = SimpleNamespace(
        global_data_dir=tmp_path
    )
    fake_out.save_data = MagicMock(return_value=str(tmp_path / "x.json"))
    fake_out.get_artifacts.return_value = []

    cfg = SimpleNamespace(analysis=SimpleNamespace(corrections=_corrections_config()))
    decisions = [
        Decision(
            candidate_id=cand.candidate_id,
            decision="apply_all",
            new_rule=CorrectionRule(
                type="token",
                wrong=["bar"],
                right="Bar",
                scope="global",
                confidence=0.8,
            ),
        ),
        Decision(candidate_id=cand.candidate_id, decision="apply_some"),
    ]

    monkeypatch.setattr(wf, "create_output_service", lambda *a, **k: fake_out)
    monkeypatch.setattr(wf, "load_memory", lambda **k: memory)
    monkeypatch.setattr(wf, "detect_memory_hits", lambda *a, **k: [cand])
    monkeypatch.setattr(wf, "detect_acronym_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_consistency_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_fuzzy_candidates", lambda *a, **k: [])
    monkeypatch.setattr(
        wf, "apply_corrections", lambda **k: ([{"text": "Foo"}], [{"status": "applied"}])
    )
    promote = MagicMock()
    monkeypatch.setattr(wf, "promote_rule", promote)
    monkeypatch.setattr(wf, "compute_transcript_identity_hash", lambda s: "key")
    monkeypatch.setattr(wf, "_derive_speaker_map", lambda *a, **k: {})

    result = wf.run_corrections_on_segments(
        segments=[{"text": "foo"}],
        transcript_path=str(tmp_path / "t.json"),
        config=cfg,
        decisions=decisions,
        apply_changes=True,
    )
    assert result["status"] == "success"
    assert promote.called


@pytest.mark.unit
def test_run_corrections_on_segments_interactive(tmp_path, monkeypatch):
    cand = _candidate()
    fake_out = MagicMock()
    fake_out.base_name = "sample"
    fake_out.get_output_structure.return_value = SimpleNamespace(
        global_data_dir=tmp_path
    )
    fake_out.save_data = MagicMock(return_value=str(tmp_path / "d.json"))
    fake_out.get_artifacts.return_value = []
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            corrections=_corrections_config(interactive_review=True)
        )
    )
    decisions = [Decision(candidate_id=cand.candidate_id, decision="skip")]

    monkeypatch.setattr(wf, "create_output_service", lambda *a, **k: fake_out)
    monkeypatch.setattr(wf, "load_memory", lambda **k: CorrectionMemory())
    monkeypatch.setattr(wf, "detect_memory_hits", lambda *a, **k: [cand])
    monkeypatch.setattr(wf, "detect_acronym_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_consistency_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "detect_fuzzy_candidates", lambda *a, **k: [])
    monkeypatch.setattr(wf, "review_candidates", lambda *a, **k: decisions)
    monkeypatch.setattr(wf, "compute_transcript_identity_hash", lambda s: "key")
    monkeypatch.setattr(wf, "_derive_speaker_map", lambda *a, **k: {})

    result = wf.run_corrections_on_segments(
        segments=[{"text": "foo"}],
        transcript_path=str(tmp_path / "t.json"),
        config=cfg,
        apply_changes=False,
    )
    assert result["status"] == "suggestions_only"
    assert result["decisions_path"]


@pytest.mark.unit
def test_run_corrections_workflow_updates_original(tmp_path, monkeypatch):
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            corrections=_corrections_config(update_original_file=True)
        )
    )
    monkeypatch.setattr(wf, "load_segments", lambda p: [{"text": "foo"}])
    monkeypatch.setattr(wf, "compute_transcript_identity_hash", lambda s: "key")
    monkeypatch.setattr(wf, "_derive_speaker_map", lambda *a, **k: {})
    monkeypatch.setattr(
        wf,
        "run_corrections_on_segments",
        lambda **k: {
            "status": "success",
            "applied_count": 1,
            "updated_segments": [{"text": "Foo"}],
        },
    )
    write = MagicMock()
    monkeypatch.setattr(wf, "_write_updated_transcript", write)
    out = wf.run_corrections_workflow(
        str(tmp_path / "t.json"), interactive=False, config=cfg
    )
    assert out["status"] == "success"
    write.assert_called_once()

    # missing corrections config
    cfg_none = SimpleNamespace(analysis=SimpleNamespace(corrections=None))
    skipped = wf.run_corrections_workflow(str(tmp_path / "t.json"), config=cfg_none)
    assert skipped["status"] == "skipped"


@pytest.mark.unit
def test_derive_speaker_map(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.corrections.workflow.SpeakerMapResolver",
        lambda: SimpleNamespace(
            load_mapping=lambda path: SimpleNamespace(speaker_map={"0": "Alice"})
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.corrections.workflow.set_speaker_display_map", MagicMock()
    )
    monkeypatch.setattr(
        "transcriptx.core.corrections.workflow.get_unique_speakers",
        lambda segs: {0: "Alice"},
    )
    assert wf._derive_speaker_map([{"text": "a"}], "/tmp/t.json") == {0: "Alice"}
