"""Tests for the sticky context bar presentation."""

from __future__ import annotations

from types import SimpleNamespace

import transcriptx.web.components.context_bar as context_bar


class _FakeSt:
    def __init__(self):
        self.markdown_calls: list[str] = []

    def markdown(self, body, **_kwargs):
        self.markdown_calls.append(body)


def test_context_bar_transcript_line(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(context_bar, "st", fake)
    monkeypatch.setattr(context_bar, "_cheap_slug_labels", lambda: {"slug": "Suzanne"})
    monkeypatch.setattr(
        context_bar.SubjectService,
        "resolve_current_subject",
        staticmethod(
            lambda _ss: SimpleNamespace(
                subject_type="transcript",
                display=SimpleNamespace(name="file_stem"),
            )
        ),
    )
    context_bar.render_context_bar(
        {
            "subject_type": "transcript",
            "subject_id": "slug",
            "run_id": "20260713_022448_09488448",
        }
    )
    assert len(fake.markdown_calls) == 1
    joined = "\n".join(fake.markdown_calls)
    assert "tx-context-bar-wrap" in joined
    assert "Suzanne / Run 13 Jul 2026, 02:24" in joined
    assert " · Transcript · " not in joined
    assert (
        "20260713_022448_09488448"
        not in joined.split("tx-context-line")[1].split("tx-run-id-info")[0]
    )
    assert "Full run identifier" in joined
    assert "20260713_022448_09488448" in joined


def test_context_bar_group_and_empty_states(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(context_bar, "st", fake)
    monkeypatch.setattr(context_bar, "_cheap_slug_labels", lambda: {})
    monkeypatch.setattr(
        context_bar.SubjectService,
        "resolve_current_subject",
        staticmethod(
            lambda _ss: SimpleNamespace(
                subject_type="group",
                display=SimpleNamespace(name="Ops group"),
            )
        ),
    )
    context_bar.render_context_bar(
        {"subject_type": "group", "subject_id": "g1", "run_id": "opaque"}
    )
    joined = "\n".join(fake.markdown_calls)
    assert "Ops group / Run selected" in joined
    assert "Group" not in joined.split("tx-context-line")[1].split("</span>")[0]

    fake2 = _FakeSt()
    monkeypatch.setattr(context_bar, "st", fake2)
    monkeypatch.setattr(
        context_bar.SubjectService,
        "resolve_current_subject",
        staticmethod(lambda _ss: None),
    )
    context_bar.render_context_bar({"subject_type": "transcript", "subject_id": None})
    joined2 = "\n".join(fake2.markdown_calls)
    assert 'tx-context-line">' in joined2
    assert "No transcript" not in joined2
    assert "No run" not in joined2
    # Empty selection → blank primary text inside the context line span.
    assert '<span class="tx-context-line"></span>' in joined2
