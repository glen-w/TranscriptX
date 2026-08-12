"""Tests for the accessible run-id info control."""

from __future__ import annotations

from transcriptx.web.components import run_id_info


def test_build_run_id_info_html_escapes_and_is_accessible():
    html_out = run_id_info.build_run_id_info_html('run_<script>"x"', control_id="tip-1")
    assert "<script>" not in html_out
    assert "run_&lt;script&gt;" in html_out or "&lt;script&gt;" in html_out
    assert 'tabindex="0"' in html_out
    assert "Full run identifier" in html_out
    assert 'role="tooltip"' in html_out
    assert 'id="tip-1"' in html_out
    assert "tx-run-id-info-tip" in html_out
    assert "aria-describedby" in html_out


def test_build_run_id_info_html_ignores_instructional_tip_prefs(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: False,
    )
    html_out = run_id_info.build_run_id_info_html("run_abc", control_id="tip-on")
    assert "ⓘ" in html_out
    assert "run_abc" in html_out


def test_render_run_id_info_control_skips_empty_and_does_not_mutate(monkeypatch):
    calls: list[str] = []
    state: dict = {"kept": 1}

    class _FakeSt:
        session_state = state

        @staticmethod
        def markdown(body, **_kwargs):
            calls.append(body)

    monkeypatch.setattr(run_id_info, "st", _FakeSt)
    run_id_info.render_run_id_info_control(None)
    run_id_info.render_run_id_info_control("")
    assert calls == []
    assert state == {"kept": 1}

    run_id_info.render_run_id_info_control("20260713_022448_09488448", key="k1")
    assert len(calls) == 1
    assert "20260713_022448_09488448" in calls[0]
    assert state == {"kept": 1}
