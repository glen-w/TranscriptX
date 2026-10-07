"""Gazetteer policy and fuzzy name clustering."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.names.catalog import build_names_catalog
from transcriptx.core.analysis.names.clustering import names_are_fuzzy_same_person
from transcriptx.core.speaker_profiles.identify.mentions import title_person_name
from transcriptx.core.speaker_profiles.identify.name_gazetteer import (
    set_gazetteer_for_tests,
)
from transcriptx.core.speaker_profiles.identify.settings import IdentifySettings


@pytest.fixture(autouse=True)
def _restore_gazetteer():
    yield
    set_gazetteer_for_tests(given=None, surnames=None)


@pytest.mark.unit
def test_hybrid_rejects_unknown_single_token(monkeypatch) -> None:
    set_gazetteer_for_tests(given=["Maya"], surnames=["Chen"])
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.mentions.load_identify_settings",
        lambda: IdentifySettings(name_token_policy="hybrid"),
    )
    assert title_person_name("Maya") == "Maya"
    assert title_person_name("Xylia") == ""
    assert title_person_name("Maya Chen") == "Maya Chen"
    assert title_person_name("Xylia Voron") == ""


@pytest.mark.unit
def test_soft_policy_keeps_unknown_tokens(monkeypatch) -> None:
    set_gazetteer_for_tests(given=["Maya"], surnames=["Chen"])
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.mentions.load_identify_settings",
        lambda: IdentifySettings(name_token_policy="soft"),
    )
    assert title_person_name("Xylia Voron") == "Xylia Voron"


@pytest.mark.unit
def test_hybrid_crm_gate_admits_unknown_full_name(monkeypatch) -> None:
    from transcriptx.core.speaker_profiles.identify.twenty import (
        PersonHit,
        TwentyPeopleIndex,
    )

    set_gazetteer_for_tests(given=["Maya"], surnames=["Chen"])
    settings = IdentifySettings(
        name_token_policy="hybrid",
        twenty_enabled=True,
        twenty_role="gate",
    )
    index = TwentyPeopleIndex(
        people=[
            PersonHit(
                twenty_id="1",
                first_name="Xylia",
                last_name="Voron",
                display_name="Xylia Voron",
            )
        ]
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.mentions.load_identify_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.mentions._crm_admits",
        lambda display, ident: display == "Xylia Voron",
    )
    assert title_person_name("Xylia Voron", settings=settings) == "Xylia Voron"
    assert title_person_name("Unknown Person", settings=settings) == ""
    assert index.people[0].identity_name() == "Xylia Voron"


@pytest.mark.unit
def test_identify_settings_v1_file_loads(tmp_path) -> None:
    from transcriptx.core.speaker_profiles.identify.settings import (
        IDENTIFY_SETTINGS_SCHEMA_VERSION,
        load_identify_settings,
        save_identify_settings,
        IdentifySettings,
    )

    path = tmp_path / "identify.json"
    path.write_text(
        '{"schema_version": 1, "auto_name": true, "auto_link": false, '
        '"style_only_apply": false}',
        encoding="utf-8",
    )
    loaded = load_identify_settings(config_dir=tmp_path)
    assert loaded.auto_name is True
    assert loaded.name_token_policy == "hybrid"
    assert loaded.twenty_enabled is False
    save_identify_settings(loaded, config_dir=tmp_path)
    saved = IdentifySettings.model_validate_json(path.read_text(encoding="utf-8"))
    assert saved.schema_version == IDENTIFY_SETTINGS_SCHEMA_VERSION


@pytest.mark.unit
def test_fuzzy_quentin_cluster() -> None:
    assert names_are_fuzzy_same_person("Quentin Hannock", "Quentin Hennick")
    assert names_are_fuzzy_same_person("Quentin Hannock", "Quinton Hannick")
    assert not names_are_fuzzy_same_person("John Smith", "Jane Smith")
    assert not names_are_fuzzy_same_person("Maya", "Mario")

    catalog = build_names_catalog(
        [
            {"surface": "Quentin Hannock", "speaker": "SPEAKER_00", "text": "a"},
            {"surface": "Quentin Hennick", "speaker": "SPEAKER_01", "text": "b"},
            {"surface": "Quinton Hannick", "speaker": "SPEAKER_00", "text": "c"},
        ]
    )
    people = catalog["people"]
    assert len(people) == 1
    assert people[0]["mention_count"] == 3
    assert people[0]["display_name"].startswith("Quentin") or people[0][
        "display_name"
    ].startswith("Quinton")
