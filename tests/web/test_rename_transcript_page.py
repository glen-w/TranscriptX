"""Rename Transcript page contracts: nav, sticky form, post-rename, capabilities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.action_menus.catalog import SECTION_ALLOWLISTS
from transcriptx.web.action_menus.context import (
    ActionContext,
    build_canonical_identity,
    capabilities_from_context,
)
from transcriptx.web.action_menus.ids import ActionId, NavStyle, SectionId
from transcriptx.web.action_menus.services import (
    PAGE_RENAME_TRANSCRIPT,
    go_rename,
)
from transcriptx.web.components.rename_form import (
    bind_suggested_rename_name,
    sticky_suggested_name_keys,
)
from transcriptx.web.navigation import navigate_to_rename_transcript
from transcriptx.web.services.rename_service import RenameResult
from transcriptx.web.state import PAGE_KEY, WORKFLOW_NAV_TRANSCRIPT_PATH


@pytest.mark.unit
def test_navigate_to_library_rename_workflow_removed() -> None:
    import transcriptx.web.navigation as nav

    assert not hasattr(nav, "navigate_to_library_rename_workflow")
    assert callable(nav.navigate_to_rename_transcript)


@pytest.mark.unit
def test_go_rename_opens_rename_transcript_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.action_menus.services as services

    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    fake_ss: dict = {}

    def _nav(ss, path):
        navigate_to_rename_transcript(ss, path)

    monkeypatch.setattr(services, "navigate_to_rename_transcript", _nav)
    monkeypatch.setattr(services, "st", SimpleNamespace(session_state=fake_ss))
    monkeypatch.setattr(
        "transcriptx.web.navigation.make_session_path_resolver",
        lambda: (lambda _p: ("slug-a", None)),
    )

    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id="meeting",
        transcript_path=transcript,
    )
    go_rename(identity)
    assert fake_ss[PAGE_KEY] == PAGE_RENAME_TRANSCRIPT
    assert fake_ss[WORKFLOW_NAV_TRANSCRIPT_PATH] == str(transcript)


@pytest.mark.unit
def test_library_allowlist_includes_rename_but_capability_still_gates() -> None:
    assert ActionId.RENAME in SECTION_ALLOWLISTS[SectionId.LIBRARY_SELECTED]

    no_path = build_canonical_identity(
        subject_type="transcript",
        subject_id="x",
        transcript_path=None,
    )
    ctx = ActionContext(
        identity=no_path,
        widget_identity="t",
        nav_style=NavStyle.CLICK_RERUN,
        instance_prefix="t",
        rename_supported=True,
    )
    caps = capabilities_from_context(ctx)
    assert caps.rename_supported is False

    disabled = build_canonical_identity(
        subject_type="transcript",
        subject_id="x",
        transcript_path="/tmp/does-not-need-to-exist.json",
    )
    ctx2 = ActionContext(
        identity=disabled,
        widget_identity="t",
        nav_style=NavStyle.CLICK_RERUN,
        instance_prefix="t",
        rename_supported=False,
    )
    assert capabilities_from_context(ctx2).rename_supported is False


@pytest.mark.unit
def test_sticky_suggested_name_survives_rerun_until_path_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.components.rename_form as form_mod

    a = tmp_path / "251230_alpha.json"
    b = tmp_path / "plain.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    ss: dict = {}
    monkeypatch.setattr(form_mod, "st", SimpleNamespace(session_state=ss))
    monkeypatch.setattr(form_mod, "_prefill_date_prefix_enabled", lambda: True)
    monkeypatch.setattr(
        form_mod,
        "_input_rename_settings",
        lambda: ("off", "{yymmdd}_{period}_{n}", True),
    )

    form_key = "test_rename_form"
    suggested = bind_suggested_rename_name(
        a, form_key=form_key, date_prefix_prefill=True
    )
    assert suggested == "251230_alpha"
    _, target_key, _ = sticky_suggested_name_keys(form_key)
    ss[target_key] = "251230_alpha_edited"

    # Same path: edit preserved
    bind_suggested_rename_name(a, form_key=form_key, date_prefix_prefill=True)
    assert ss[target_key] == "251230_alpha_edited"

    # Switch transcript: reset to new suggestion
    next_name = bind_suggested_rename_name(
        b, form_key=form_key, date_prefix_prefill=True
    )
    assert "plain" in next_name
    assert ss[target_key] == next_name
    assert ss[target_key] != "251230_alpha_edited"


@pytest.mark.unit
def test_sticky_smart_rename_prefills_date_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.components.rename_form as form_mod
    from transcriptx.web.components.rename_form import sticky_smart_rename_keys

    path = tmp_path / "R20260810-173237.json"
    path.write_text("{}", encoding="utf-8")
    ss: dict = {}
    monkeypatch.setattr(form_mod, "st", SimpleNamespace(session_state=ss))
    monkeypatch.setattr(
        form_mod,
        "_input_rename_settings",
        lambda: ("suggest_rename_only", "{yymmdd}_{period}_{n}", True),
    )

    form_key = "smart_rename_form"
    suggested = bind_suggested_rename_name(
        path, form_key=form_key, date_prefix_prefill=True, enable_smart=True
    )
    assert suggested == "260810_"
    bubbles_key, date_root_key = sticky_smart_rename_keys(form_key)
    assert ss[date_root_key] == "260810_"
    assert "evening" in ss[bubbles_key]
    assert "1" in ss[bubbles_key]


@pytest.mark.unit
def test_post_rename_clears_old_path_and_binds_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.rename_transcript as page

    old = tmp_path / "old.json"
    new = tmp_path / "251230_new.json"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")

    ss: dict = {
        WORKFLOW_NAV_TRANSCRIPT_PATH: str(old),
        page._SELECTED_PATH_KEY: str(old),
        page._PICKER_KEY: 1,
        page.rename_play_key(old): 0,
    }
    monkeypatch.setattr(page, "st", SimpleNamespace(session_state=ss))
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form.st",
        SimpleNamespace(session_state=ss),
    )
    monkeypatch.setattr(
        page,
        "SubjectService",
        SimpleNamespace(
            set_transcript_context_from_path=lambda *a, **k: None,
        ),
    )
    monkeypatch.setattr(page, "make_session_path_resolver", lambda: (lambda _p: None))
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form._prefill_date_prefix_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form._input_rename_settings",
        lambda: ("off", "{yymmdd}_{period}_{n}", True),
    )

    result = RenameResult(
        ok=True,
        message="ok",
        old_base_name="old",
        new_base_name="251230_new",
        old_transcript_path=str(old),
        new_transcript_path=str(new),
        transaction_committed=True,
    )
    page.apply_rename_page_post_rename(result)

    assert WORKFLOW_NAV_TRANSCRIPT_PATH not in ss
    assert page._PICKER_KEY not in ss
    assert ss[page._SELECTED_PATH_KEY] == str(new)
    assert (
        page.rename_play_key(old) not in ss or ss.get(page.rename_play_key(old)) is None
    )
    bound, target, _ = sticky_suggested_name_keys(page._FORM_KEY)
    assert str(new) in str(ss.get(bound, "")) or Path(ss[bound]).name == new.name
    assert "251230_new" in str(ss.get(target, ""))


@pytest.mark.unit
def test_rename_page_and_library_presence() -> None:
    import transcriptx.web.page_modules.library as library
    import transcriptx.web.page_modules.rename_transcript as rename_page
    from transcriptx.web.navigation import PAGE_SPECS
    from transcriptx.web.router import build_page_renderers

    lib_src = Path(library.__file__).read_text(encoding="utf-8")
    assert "library_rename_form" not in lib_src
    assert "render_transcript_rename_form" not in lib_src
    assert "LIBRARY_SELECTED" in lib_src

    rename_src = Path(rename_page.__file__).read_text(encoding="utf-8")
    assert "rename_transcript_page_form" in rename_src
    assert "render_exact_segment_preview" in rename_src
    assert "autoplay=True" in rename_src
    assert "date_prefix_prefill=True" in rename_src

    assert any(s.key == "Rename Transcript" for s in PAGE_SPECS)
    renderers = build_page_renderers(
        corrections_studio_available=False, render_corrections_studio=None
    )
    assert "Rename Transcript" in renderers


@pytest.mark.unit
def test_library_rename_action_to_preview_rename_smoke(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Library allowlist → go_rename → Rename page subject → post-rename new path."""
    import transcriptx.web.action_menus.services as services
    import transcriptx.web.page_modules.rename_transcript as page

    transcript = tmp_path / "call.json"
    renamed = tmp_path / "251230_call_renamed.json"
    transcript.write_text(
        '{"segments":[{"start":0,"end":1,"text":"hello","speaker":"SPEAKER_00"}]}',
        encoding="utf-8",
    )
    renamed.write_text(
        '{"segments":[{"start":0,"end":1,"text":"hello","speaker":"SPEAKER_00"}]}',
        encoding="utf-8",
    )

    assert ActionId.RENAME in SECTION_ALLOWLISTS[SectionId.LIBRARY_SELECTED]

    ss: dict = {}
    monkeypatch.setattr(services, "st", SimpleNamespace(session_state=ss))
    monkeypatch.setattr(
        "transcriptx.web.navigation.make_session_path_resolver",
        lambda: (lambda _p: ("slug-call", None)),
    )
    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id="call",
        transcript_path=transcript,
    )
    go_rename(identity)
    assert ss[PAGE_KEY] == "Rename Transcript"
    assert ss[WORKFLOW_NAV_TRANSCRIPT_PATH] == str(transcript)

    # Simulate page consuming nav + binding form, then rename success.
    monkeypatch.setattr(page, "st", SimpleNamespace(session_state=ss))
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form.st",
        SimpleNamespace(session_state=ss),
    )
    monkeypatch.setattr(
        page,
        "SubjectService",
        SimpleNamespace(set_transcript_context_from_path=lambda *a, **k: None),
    )
    monkeypatch.setattr(page, "make_session_path_resolver", lambda: (lambda _p: None))
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form._prefill_date_prefix_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "transcriptx.web.components.rename_form._input_rename_settings",
        lambda: ("off", "{yymmdd}_{period}_{n}", True),
    )

    nav_path = ss.pop(WORKFLOW_NAV_TRANSCRIPT_PATH)
    ss[page._SELECTED_PATH_KEY] = nav_path
    bind_suggested_rename_name(
        nav_path, form_key=page._FORM_KEY, date_prefix_prefill=True
    )
    ss[page.rename_play_key(nav_path)] = 0

    page.apply_rename_page_post_rename(
        RenameResult(
            ok=True,
            message="ok",
            old_transcript_path=str(transcript),
            new_transcript_path=str(renamed),
            transaction_committed=True,
        )
    )
    assert WORKFLOW_NAV_TRANSCRIPT_PATH not in ss
    assert ss[page._SELECTED_PATH_KEY] == str(renamed)
    assert ss.get(page.rename_play_key(transcript)) in (None,)
    # No stale old-path form binding
    bound_key, _, _ = sticky_suggested_name_keys(page._FORM_KEY)
    assert str(transcript.resolve()) not in str(ss.get(bound_key, ""))
