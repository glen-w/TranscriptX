"""Core tests for interface action-menu prefs, catalogue, and resolve."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.action_menus.catalog import (
    ACTIONS,
    ACTIONS_BY_ID,
    OPTIONAL_ACTIONS,
    SECTION_ALLOWLISTS,
    SECTION_DEFAULTS,
    section_default_actions,
)
from transcriptx.web.action_menus.context import (
    ActionContext,
    IdentityError,
    build_canonical_identity,
    capabilities_from_context,
)
from transcriptx.web.action_menus.handlers import HANDLERS, is_action_available
from transcriptx.web.action_menus.ids import (
    SECTION_ORDER,
    ActionId,
    NavStyle,
    SectionId,
)
from transcriptx.web.action_menus.prefs import (
    built_in_prefs,
    load_interface_prefs,
    merge_prefs,
    replace_with_built_in_defaults,
    reset_draft_to_built_ins,
    save_interface_prefs,
    sanitise_action_ids,
    validate_draft_for_save,
)
from transcriptx.web.action_menus.resolve import (
    configured_actions_for_section,
    resolve_section_actions,
)


def test_catalogue_invariants() -> None:
    assert len(ACTIONS) == len({a.id for a in ACTIONS})
    for action in ACTIONS:
        assert action.label
        assert action.icon
        assert action.help
        assert action.id in HANDLERS
    for sid, allow in SECTION_ALLOWLISTS.items():
        for aid in allow:
            assert aid in ACTIONS_BY_ID
            assert aid in HANDLERS
    for key, defaults in SECTION_DEFAULTS.items():
        assert defaults, f"empty default for {key}"
        allow = set(SECTION_ALLOWLISTS[key.section])
        for aid in defaults:
            assert aid in allow
    for aid in OPTIONAL_ACTIONS:
        for defaults in SECTION_DEFAULTS.values():
            assert aid not in defaults


def test_built_in_standard_excludes_optional() -> None:
    prefs = built_in_prefs()
    for sid in SECTION_ORDER:
        configured = configured_actions_for_section(
            prefs, sid, subject_type="transcript", has_run=True
        )
        for opt in OPTIONAL_ACTIONS:
            assert opt not in configured


@pytest.mark.parametrize(
    ("section", "subject_type", "has_run", "expected"),
    [
        (
            SectionId.HOME_RECENT_RUNS,
            "transcript",
            True,
            [
                ActionId.OPEN,
                ActionId.CHARTS,
                ActionId.ARTIFACTS,
                ActionId.EXPORT_ZIP,
                ActionId.RENAME,
            ],
        ),
        (
            SectionId.LIBRARY_SELECTED,
            "transcript",
            False,
            [ActionId.RUN_SPEAKER_ID, ActionId.RUN_ANALYSIS],
        ),
        (
            SectionId.IMPORT_SUCCESS,
            "transcript",
            False,
            [
                ActionId.OPEN_LIBRARY,
                ActionId.RUN_ANALYSIS,
                ActionId.RUN_SPEAKER_ID,
            ],
        ),
        (
            SectionId.SPEAKER_ID_COMPLETE,
            "transcript",
            True,
            [
                ActionId.OPEN,
                ActionId.CHARTS,
                ActionId.ARTIFACTS,
                ActionId.EXPORT_ZIP,
                ActionId.RENAME,
            ],
        ),
        (
            SectionId.SPEAKER_ID_COMPLETE,
            "transcript",
            False,
            [ActionId.OPEN, ActionId.RUN_ANALYSIS, ActionId.RENAME],
        ),
        (
            SectionId.RUN_ANALYSIS_COMPLETE,
            "transcript",
            True,
            [
                ActionId.OPEN,
                ActionId.CHARTS,
                ActionId.ARTIFACTS,
                ActionId.EXPORT_ZIP,
                ActionId.RENAME,
            ],
        ),
        (
            SectionId.RUN_ANALYSIS_COMPLETE,
            "group",
            True,
            [ActionId.OPEN, ActionId.CHARTS, ActionId.ARTIFACTS],
        ),
    ],
)
def test_section_default_regression(
    section: SectionId,
    subject_type: str,
    has_run: bool,
    expected: list[ActionId],
) -> None:
    assert (
        list(
            section_default_actions(section, subject_type=subject_type, has_run=has_run)
        )
        == expected
    )
    prefs = built_in_prefs()
    assert (
        configured_actions_for_section(
            prefs, section, subject_type=subject_type, has_run=has_run
        )
        == expected
    )


def test_sanitise_drops_unknown_and_duplicates() -> None:
    assert sanitise_action_ids(
        ["open", "bogus", "charts", "open", ActionId.ARTIFACTS]
    ) == [ActionId.OPEN, ActionId.CHARTS, ActionId.ARTIFACTS]


def test_show_menu_off_resolves_empty() -> None:
    prefs = built_in_prefs()
    prefs.sections[SectionId.HOME_RECENT_RUNS].show_menu = False
    assert (
        configured_actions_for_section(
            prefs, SectionId.HOME_RECENT_RUNS, subject_type="transcript", has_run=True
        )
        == []
    )


def test_identity_rejects_mismatched_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "slug" / "run-a"
    run_dir.mkdir(parents=True)
    with pytest.raises(IdentityError):
        build_canonical_identity(
            subject_type="transcript",
            subject_id="slug",
            run_id="run-b",
            run_dir=run_dir,
        )


def test_open_available_without_run(tmp_path: Path) -> None:
    tp = tmp_path / "t.json"
    tp.write_text("{}", encoding="utf-8")
    ident = build_canonical_identity(
        subject_type="transcript", subject_id="slug", transcript_path=tp
    )
    ctx = ActionContext(
        identity=ident,
        widget_identity="w1",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="t",
        run_completed=False,
    )
    caps = capabilities_from_context(ctx)
    assert caps.has_transcript_path
    assert not caps.has_valid_run
    assert is_action_available(ActionId.OPEN, ctx, caps)
    assert not is_action_available(ActionId.CHARTS, ctx, caps)
    assert not is_action_available(ActionId.EXPORT_ZIP, ctx, caps)


def test_insights_requires_completed_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "slug" / "run-a"
    run_dir.mkdir(parents=True)
    ident = build_canonical_identity(
        subject_type="transcript",
        subject_id="slug",
        run_id="run-a",
        run_dir=run_dir,
    )
    ctx = ActionContext(
        identity=ident,
        widget_identity="w",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="t",
        run_completed=False,
    )
    caps = capabilities_from_context(ctx)
    assert not is_action_available(ActionId.INSIGHTS, ctx, caps)
    ctx2 = ActionContext(
        identity=ident,
        widget_identity="w",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="t",
        run_completed=True,
    )
    assert is_action_available(ActionId.INSIGHTS, ctx2, capabilities_from_context(ctx2))


def test_corrections_excluded_for_group(tmp_path: Path) -> None:
    run_dir = tmp_path / "g1" / "run-a"
    run_dir.mkdir(parents=True)
    ident = build_canonical_identity(
        subject_type="group",
        subject_id="g1",
        run_id="run-a",
        run_dir=run_dir,
    )
    ctx = ActionContext(
        identity=ident,
        widget_identity="w",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="t",
        corrections_workspace_available=True,
        run_completed=True,
    )
    caps = capabilities_from_context(ctx)
    assert not is_action_available(ActionId.CORRECTIONS, ctx, caps)
    assert not is_action_available(ActionId.OPEN_TRANSCRIPT, ctx, caps)


def test_load_save_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "interface_menus.json"
    prefs, draft = load_interface_prefs(path)
    assert not draft.recovery
    prefs.sections[SectionId.LIBRARY_SELECTED].mode = "manual"
    prefs.sections[SectionId.LIBRARY_SELECTED].selected = [
        ActionId.RUN_ANALYSIS,
        ActionId.OPEN_TRANSCRIPT,
    ]
    draft.prefs = prefs
    result = save_interface_prefs(draft, path=path)
    assert result.ok
    prefs2, draft2 = load_interface_prefs(path)
    assert not draft2.recovery
    assert prefs2.sections[SectionId.LIBRARY_SELECTED].selected == [
        ActionId.OPEN_TRANSCRIPT,
        ActionId.RUN_ANALYSIS,
    ]


def test_stale_save_conflict(tmp_path: Path) -> None:
    path = tmp_path / "interface_menus.json"
    _, draft_a = load_interface_prefs(path)
    save_interface_prefs(draft_a, path=path)
    _, draft_b = load_interface_prefs(path)
    draft_a.prefs.standard_menu_mode = "custom"
    draft_a.prefs.standard_menu = [ActionId.OPEN]
    assert save_interface_prefs(draft_a, path=path).ok
    draft_b.prefs.standard_menu_mode = "custom"
    draft_b.prefs.standard_menu = [ActionId.CHARTS]
    result = save_interface_prefs(draft_b, path=path)
    assert not result.ok
    assert result.conflict


def test_malformed_file_recovery(tmp_path: Path) -> None:
    path = tmp_path / "interface_menus.json"
    path.write_text("{not-json", encoding="utf-8")
    prefs, draft = load_interface_prefs(path)
    assert draft.recovery
    assert prefs.model_dump() == built_in_prefs().model_dump()
    result = save_interface_prefs(draft, path=path)
    assert not result.ok
    result2 = replace_with_built_in_defaults(draft, path=path)
    assert result2.ok
    assert not draft.recovery
    backups = list(tmp_path.glob("interface_menus.json.bak.*"))
    assert backups


def test_future_schema_preserved(tmp_path: Path) -> None:
    path = tmp_path / "interface_menus.json"
    path.write_text('{"schema_version": 99, "prefs": {}}\n', encoding="utf-8")
    original = path.read_bytes()
    _, draft = load_interface_prefs(path)
    assert draft.recovery
    assert path.read_bytes() == original
    assert not save_interface_prefs(draft, path=path).ok


def test_restore_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "interface_menus.json"
    _, draft = load_interface_prefs(path)
    draft.prefs.standard_menu_mode = "custom"
    draft.prefs.standard_menu = [ActionId.OPEN]
    save_interface_prefs(draft, path=path)
    before = path.read_bytes()
    ss: dict = {"interface_menus_draft": draft}
    reset_draft_to_built_ins(ss)
    assert path.read_bytes() == before
    assert ss["interface_menus_draft"].prefs.standard_menu_mode == "built_in"


def test_validate_empty_manual() -> None:
    prefs = built_in_prefs()
    prefs.sections[SectionId.LIBRARY_SELECTED].mode = "manual"
    prefs.sections[SectionId.LIBRARY_SELECTED].selected = []
    assert validate_draft_for_save(prefs)


def test_merge_missing_sections() -> None:
    merged = merge_prefs({"standard_menu_mode": "built_in", "sections": {}})
    assert set(merged.sections) == set(SECTION_ORDER)


def test_merge_show_info_tooltips_defaults_true_and_round_trips() -> None:
    assert merge_prefs({"sections": {}}).show_info_tooltips is True
    assert (
        merge_prefs({"show_info_tooltips": False, "sections": {}}).show_info_tooltips
        is False
    )
    assert (
        merge_prefs({"show_info_tooltips": "nope", "sections": {}}).show_info_tooltips
        is True
    )
    built = built_in_prefs()
    assert built.show_info_tooltips is True


def test_export_key_suffix_differs_across_subjects(tmp_path: Path) -> None:
    run_a = tmp_path / "slug-a" / "run-1"
    run_b = tmp_path / "slug-b" / "run-1"
    run_a.mkdir(parents=True)
    run_b.mkdir(parents=True)
    i1 = build_canonical_identity(
        subject_type="transcript",
        subject_id="slug-a",
        run_id="run-1",
        run_dir=run_a,
    )
    i2 = build_canonical_identity(
        subject_type="transcript",
        subject_id="slug-b",
        run_id="run-1",
        run_dir=run_b,
    )
    assert i1.export_key_suffix != i2.export_key_suffix


def test_resolve_filters_unavailable(tmp_path: Path) -> None:
    tp = tmp_path / "t.json"
    tp.write_text("{}", encoding="utf-8")
    prefs = built_in_prefs()
    prefs.sections[SectionId.SPEAKER_ID_COMPLETE].mode = "manual"
    prefs.sections[SectionId.SPEAKER_ID_COMPLETE].selected = [
        ActionId.OPEN,
        ActionId.CHARTS,
        ActionId.EXPORT_ZIP,
    ]
    ident = build_canonical_identity(
        subject_type="transcript", subject_id="slug", transcript_path=tp
    )
    ctx = ActionContext(
        identity=ident,
        widget_identity="w",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="t",
    )
    resolved = resolve_section_actions(SectionId.SPEAKER_ID_COMPLETE, ctx, prefs=prefs)
    assert resolved == [ActionId.OPEN]


def test_no_statistics_action() -> None:
    assert "statistics" not in {a.value for a in ActionId}
