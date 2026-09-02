"""Diagnostics page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_diagnostics_renders_doctor_and_rename_sections(monkeypatch) -> None:
    import transcriptx.web.page_modules.diagnostics as mod

    DummyHomeStreamlit.session_state = {}
    markdowns: list = []
    rename_calls: list = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(text, **_k):
            markdowns.append(str(text))

        @staticmethod
        def subheader(*_a, **_k):
            return None

        @staticmethod
        def write(*_a, **_k):
            return None

        @staticmethod
        def text(*_a, **_k):
            return None

        @staticmethod
        def info(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "cached_doctor_report",
        lambda: {
            "config_snapshot_available": True,
            "dependency_versions": {"streamlit": "1.0"},
        },
    )
    monkeypatch.setattr(mod, "cached_group_manifest_warnings", lambda: [])
    monkeypatch.setattr(
        mod,
        "_render_rename_repair_section",
        lambda: rename_calls.append(True),
    )
    monkeypatch.setattr(mod, "_render_incomplete_runs_section", lambda: None)
    monkeypatch.setattr(mod, "_render_speaker_profile_ops", lambda: None)

    mod.render_diagnostics_page()

    assert any("Diagnostics" in m for m in markdowns)
    assert rename_calls


@pytest.mark.unit
def test_diagnostics_shows_group_manifest_warnings(monkeypatch) -> None:
    import transcriptx.web.page_modules.diagnostics as mod

    warnings: list[str] = []
    subheaders: list[str] = []
    codes: list[str] = []
    expanders: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def subheader(text, **_k):
            subheaders.append(str(text))

        @classmethod
        def warning(cls, msg, **_k):
            warnings.append(str(msg))

        @staticmethod
        def code(text, **_k):
            codes.append(str(text))

        @classmethod
        def expander(cls, label, **_k):
            expanders.append(str(label))
            return super().expander(label, **_k)

        @staticmethod
        def write(*_a, **_k):
            return None

        @staticmethod
        def text(*_a, **_k):
            return None

        @staticmethod
        def info(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "cached_doctor_report",
        lambda: {
            "config_snapshot_available": False,
            "dependency_versions": {},
        },
    )
    monkeypatch.setattr(
        mod,
        "cached_group_manifest_warnings",
        lambda: ["bad group.json"],
    )
    monkeypatch.setattr(mod, "_render_rename_repair_section", lambda: None)
    monkeypatch.setattr(mod, "_render_incomplete_runs_section", lambda: None)
    monkeypatch.setattr(mod, "_render_speaker_profile_ops", lambda: None)

    mod.render_diagnostics_page()

    assert any("Group manifests" in s for s in subheaders)
    assert warnings
    assert any("1 unloadable group manifest" in e for e in expanders)
    assert "bad group.json" in codes


@pytest.mark.unit
def test_diagnostics_invokes_incomplete_runs_section(monkeypatch) -> None:
    import transcriptx.web.page_modules.diagnostics as mod

    incomplete_calls: list = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def subheader(*_a, **_k):
            return None

        @staticmethod
        def write(*_a, **_k):
            return None

        @staticmethod
        def text(*_a, **_k):
            return None

        @staticmethod
        def info(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "cached_doctor_report",
        lambda: {"config_snapshot_available": False, "dependency_versions": {}},
    )
    monkeypatch.setattr(mod, "cached_group_manifest_warnings", lambda: [])
    monkeypatch.setattr(mod, "_render_rename_repair_section", lambda: None)
    monkeypatch.setattr(
        mod, "_render_incomplete_runs_section", lambda: incomplete_calls.append(True)
    )
    monkeypatch.setattr(mod, "_render_speaker_profile_ops", lambda: None)

    mod.render_diagnostics_page()

    assert incomplete_calls


@pytest.mark.unit
def test_incomplete_runs_section_lists_missing_run_results(
    monkeypatch, tmp_path
) -> None:
    import transcriptx.web.page_modules.diagnostics as mod
    from transcriptx.core.pipeline.incomplete_runs import IncompleteRun

    captions: list[str] = []
    warnings: list[str] = []
    markdowns: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def subheader(*_a, **_k):
            return None

        @staticmethod
        def caption(text, **_k):
            captions.append(str(text))

        @classmethod
        def warning(cls, msg, **_k):
            warnings.append(str(msg))

        @staticmethod
        def markdown(text, **_k):
            markdowns.append(str(text))

        @classmethod
        def container(cls, **_k):
            return super().container(**_k)

    run_dir = tmp_path / "slug-a" / "run-2"
    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.incomplete_runs.list_incomplete_run_dirs",
        lambda: (
            IncompleteRun(
                slug="slug-a",
                run_id="run-2",
                run_dir=run_dir,
                kind="transcript",
            ),
        ),
    )

    mod._render_incomplete_runs_section()

    assert warnings
    assert any("run-2" in m for m in markdowns)
    assert any(str(run_dir) in c for c in captions)
