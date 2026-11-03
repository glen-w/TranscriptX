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
    shell_titles: list[str] = []
    monkeypatch.setattr(
        mod, "render_page_shell", lambda title, *a, **k: shell_titles.append(title)
    )

    mod.render_diagnostics_page()

    assert shell_titles == ["Diagnostics"]
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

        @staticmethod
        def dataframe(rows, **_k):
            tables.append(list(rows))

        @staticmethod
        def number_input(*_a, **_k):
            return 1

        @staticmethod
        def button(*_a, **_k):
            return False

    tables: list[list[dict]] = []
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
    # Broken runs render as one table (not one container per run).
    assert len(tables) == 1 and len(tables[0]) == 1
    row = tables[0][0]
    assert row["Run"] == "run-2" and row["Folder"] == str(run_dir)
    assert row["State"] == "never finalized"


def _incomplete(tmp_path, n: int):
    from transcriptx.core.pipeline.incomplete_runs import IncompleteRun

    rows = []
    for i in range(n):
        run_dir = tmp_path / f"slug-{i}" / f"run-{i}"
        rows.append(
            IncompleteRun(
                slug=f"slug-{i}",
                run_id=f"run-{i}",
                run_dir=run_dir,
                kind="transcript",
            )
        )
    return tuple(rows)


@pytest.mark.unit
def test_incomplete_runs_section_paginates_fifty_per_page(
    monkeypatch, tmp_path
) -> None:
    import transcriptx.web.page_modules.diagnostics as mod

    tables: list[list[dict]] = []
    captions: list[str] = []

    class _St(DummyHomeStreamlit):
        session_state = {"diagnostics_incomplete_page": 2}

        @staticmethod
        def subheader(*_a, **_k):
            return None

        @staticmethod
        def caption(text, **_k):
            captions.append(str(text))

        @classmethod
        def warning(cls, msg, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def dataframe(rows, **_k):
            tables.append(list(rows))

        @staticmethod
        def number_input(*_a, **_k):
            return 2

        @staticmethod
        def button(*_a, **_k):
            return False

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.incomplete_runs.list_incomplete_run_dirs",
        lambda: _incomplete(tmp_path, 51),
    )

    mod._render_incomplete_runs_section()

    assert len(tables) == 1
    assert len(tables[0]) == 1
    assert tables[0][0]["Run"] == "run-50"
    assert any("51" in c for c in captions)


@pytest.mark.unit
def test_incomplete_runs_clean_opens_settings_storage(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.diagnostics as mod
    from transcriptx.web.state import PAGE_KEY, SETTINGS_HUB_TAB_KEY

    DummyHomeStreamlit.session_state = {}
    reruns: list[bool] = []
    flashes: list[tuple] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def subheader(*_a, **_k):
            return None

        @staticmethod
        def caption(*_a, **_k):
            return None

        @classmethod
        def warning(cls, *_a, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def dataframe(*_a, **_k):
            return None

        @staticmethod
        def number_input(*_a, **_k):
            return 1

        @staticmethod
        def button(*_a, **_k):
            return True

        @staticmethod
        def rerun(*_a, **_k):
            reruns.append(True)

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.core.pipeline.incomplete_runs.list_incomplete_run_dirs",
        lambda: _incomplete(tmp_path, 1),
    )
    monkeypatch.setattr(
        mod, "set_page_flash", lambda kind, msg: flashes.append((kind, msg))
    )

    mod._render_incomplete_runs_section()

    assert DummyHomeStreamlit.session_state[PAGE_KEY] == "Settings"
    assert DummyHomeStreamlit.session_state[SETTINGS_HUB_TAB_KEY] == "Storage"
    assert flashes and flashes[0][0] == "info"
    assert reruns
