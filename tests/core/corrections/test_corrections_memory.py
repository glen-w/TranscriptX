"""Unit tests for ``core.corrections.memory`` layered rule persistence.

Offline and deterministic: YAML/JSON file I/O only (no models, no network).
Global/project memory paths are redirected into ``tmp_path`` via monkeypatch so
no real user config is read or written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from transcriptx.core.corrections import memory as memory_mod
from transcriptx.core.corrections.models import CorrectionMemory, CorrectionRule


def _rule(wrong, right, scope="global", rule_type="token", **kwargs) -> CorrectionRule:
    return CorrectionRule(
        type=rule_type,
        wrong=list(wrong),
        right=right,
        scope=scope,
        **kwargs,
    )


@pytest.mark.unit
class TestProjectMemoryPath:
    def test_none_project_root_returns_none(self):
        assert memory_mod._get_project_memory_path(None) is None

    def test_prefers_primary_when_present(self, tmp_path: Path):
        (tmp_path / "transcriptx_corrections.yml").write_text("rules: {}")
        result = memory_mod._get_project_memory_path(tmp_path)
        assert result == tmp_path / "transcriptx_corrections.yml"

    def test_uses_fallback_when_only_fallback_exists(self, tmp_path: Path):
        nested = tmp_path / ".transcriptx"
        nested.mkdir()
        (nested / "corrections.yml").write_text("rules: {}")
        result = memory_mod._get_project_memory_path(tmp_path)
        assert result == nested / "corrections.yml"

    def test_defaults_to_primary_when_neither_exists(self, tmp_path: Path):
        result = memory_mod._get_project_memory_path(tmp_path)
        assert result == tmp_path / "transcriptx_corrections.yml"


@pytest.mark.unit
class TestGlobalMemoryPath:
    def test_global_path_is_under_home(self):
        path = memory_mod._get_global_memory_path()
        assert path.name == "corrections.yml"
        assert "transcriptx" in str(path)
        assert str(path).startswith(str(Path.home()))


@pytest.mark.unit
class TestLoadRulesFromYaml:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert memory_mod._load_rules_from_yaml(tmp_path / "nope.yml") == {}

    def test_invalid_yaml_returns_empty(self, tmp_path: Path):
        path = tmp_path / "bad.yml"
        path.write_text("::: not valid yaml :::\n- [unbalanced")
        assert memory_mod._load_rules_from_yaml(path) == {}

    def test_rules_wrapper_key_is_unwrapped(self, tmp_path: Path):
        path = tmp_path / "c.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "rules": {
                        "r1": {
                            "type": "token",
                            "wrong": ["wren"],
                            "right": "Wren",
                            "scope": "global",
                        }
                    }
                }
            )
        )
        rules = memory_mod._load_rules_from_yaml(path)
        assert set(rules) == {"r1"}
        assert rules["r1"].right == "Wren"

    def test_keyed_dict_key_wins_as_id(self, tmp_path: Path):
        # When the YAML key and an embedded id disagree, the key is authoritative.
        path = tmp_path / "c.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "mykey": {
                        "id": "other-id",
                        "type": "token",
                        "wrong": ["wren"],
                        "right": "Wren",
                        "scope": "global",
                    }
                }
            )
        )
        rules = memory_mod._load_rules_from_yaml(path)
        assert set(rules) == {"mykey"}
        assert rules["mykey"].id == "mykey"

    def test_list_form_is_supported(self, tmp_path: Path):
        path = tmp_path / "c.yml"
        path.write_text(
            yaml.safe_dump(
                [
                    {
                        "type": "token",
                        "wrong": ["wren"],
                        "right": "Wren",
                        "scope": "global",
                    }
                ]
            )
        )
        rules = memory_mod._load_rules_from_yaml(path)
        assert len(rules) == 1
        rule = next(iter(rules.values()))
        assert rule.right == "Wren"

    def test_invalid_rule_entries_are_skipped(self, tmp_path: Path):
        path = tmp_path / "c.yml"
        path.write_text(
            yaml.safe_dump(
                {
                    "good": {
                        "type": "token",
                        "wrong": ["x"],
                        "right": "X",
                        "scope": "global",
                    },
                    "bad": {
                        "type": "not-a-valid-type",
                        "wrong": ["y"],
                        "right": "Y",
                        "scope": "global",
                    },
                    "non_dict": ["should be skipped"],
                }
            )
        )
        rules = memory_mod._load_rules_from_yaml(path)
        assert set(rules) == {"good"}


@pytest.mark.unit
class TestLoadRulesFromDecisions:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert memory_mod._load_rules_from_decisions(tmp_path / "nope.json") == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path):
        path = tmp_path / "d.json"
        path.write_text("{not json")
        assert memory_mod._load_rules_from_decisions(path) == {}

    def test_non_list_decisions_returns_empty(self, tmp_path: Path):
        path = tmp_path / "d.json"
        path.write_text(json.dumps({"decisions": {"unexpected": "shape"}}))
        assert memory_mod._load_rules_from_decisions(path) == {}

    def test_extracts_new_rules_and_skips_others(self, tmp_path: Path):
        learned = _rule(["wren"], "Wren", scope="transcript")
        payload = {
            "decisions": [
                {
                    "candidate_id": "c1",
                    "decision": "learn",
                    "new_rule": learned.model_dump(),
                },
                {"candidate_id": "c2", "decision": "reject"},
                {"bogus": "entry"},
            ]
        }
        path = tmp_path / "d.json"
        path.write_text(json.dumps(payload))
        rules = memory_mod._load_rules_from_decisions(path)
        assert set(rules) == {learned.id}


@pytest.mark.unit
class TestSaveMemoryLayer:
    def test_roundtrip_with_loader(self, tmp_path: Path):
        path = tmp_path / "out" / "corrections.yml"
        rules = [_rule(["wren"], "Wren"), _rule(["jon"], "John")]
        memory_mod.save_memory_layer(path, rules)

        assert path.exists()
        loaded = memory_mod._load_rules_from_yaml(path)
        assert {r.right for r in loaded.values()} == {"Wren", "John"}


@pytest.mark.unit
class TestLoadMemory:
    def test_layers_merge_with_transcript_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        global_path = tmp_path / "global.yml"
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_path = project_root / "transcriptx_corrections.yml"

        # Same rule id across global/project (project should win on merge),
        # plus a transcript decision that adds another rule.
        shared = _rule(["wren"], "Wren", scope="global")
        memory_mod.save_memory_layer(global_path, [shared])
        project_variant = _rule(["wren"], "Wren", scope="project")
        memory_mod.save_memory_layer(project_path, [project_variant])

        learned = _rule(["jon"], "John", scope="transcript")
        decisions_path = tmp_path / "decisions.json"
        decisions_path.write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "candidate_id": "c1",
                            "decision": "learn",
                            "new_rule": learned.model_dump(),
                        }
                    ]
                }
            )
        )

        monkeypatch.setattr(
            memory_mod,
            "resolve_project_root",
            lambda transcript_path=None: project_root,
        )
        monkeypatch.setattr(memory_mod, "_get_global_memory_path", lambda: global_path)

        result = memory_mod.load_memory(
            transcript_path=str(tmp_path / "t.json"),
            transcript_decisions_path=str(decisions_path),
        )

        assert isinstance(result, CorrectionMemory)
        # Shared id present once, project scope wins; learned rule added.
        assert result.rules[shared.id].scope == "project"
        assert learned.id in result.rules
        assert len(result.rules) == 2


@pytest.mark.unit
class TestPromoteRule:
    def test_unknown_target_raises(self):
        with pytest.raises(ValueError):
            memory_mod.promote_rule(_rule(["x"], "X"), "nonsense")

    def test_promote_to_global_writes_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        global_path = tmp_path / "global.yml"
        monkeypatch.setattr(memory_mod, "_get_global_memory_path", lambda: global_path)
        rule = _rule(["wren"], "Wren")

        result = memory_mod.promote_rule(rule, "global")

        assert result == global_path
        loaded = memory_mod._load_rules_from_yaml(global_path)
        assert rule.id in loaded

    def test_promote_to_project_sets_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.setattr(
            memory_mod,
            "resolve_project_root",
            lambda transcript_path=None: project_root,
        )
        rule = _rule(["wren"], "Wren", scope="global")

        result = memory_mod.promote_rule(rule, "project")

        assert result == project_root / "transcriptx_corrections.yml"
        loaded = memory_mod._load_rules_from_yaml(result)
        assert loaded[rule.id].scope == "project"

    def test_promote_to_project_returns_none_without_root(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            memory_mod, "resolve_project_root", lambda transcript_path=None: None
        )
        assert memory_mod.promote_rule(_rule(["x"], "X"), "project") is None
