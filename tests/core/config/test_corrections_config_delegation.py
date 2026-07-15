"""Runtime delegation tests for analysis.corrections (Batch 5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.config.models.corrections import CorrectionsSettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig, CorrectionsConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
    without_transcriptx_env,
)

_FIELDS = tuple(
    k
    for k in CorrectionsSettingsModel.model_fields.keys()
    if k != "llm"  # nested dataclass; covered by shape / asdict parity
)


def test_llm_nested_defaults() -> None:
    from dataclasses import asdict

    expected = CorrectionsSettingsModel().model_dump()["llm"]
    assert asdict(AnalysisConfig().corrections.llm) == expected
    with without_transcriptx_env():
        assert (
            TranscriptXConfig().to_dict()["analysis"]["corrections"]["llm"] == expected
        )


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


def test_default_shape_matches_pre_delegation_snapshot() -> None:
    assert_subtree_shape_matches_pre_snapshot("corrections")


def test_asdict_parity_with_pydantic_model() -> None:
    assert asdict(CorrectionsConfig()) == CorrectionsSettingsModel().model_dump()


@pytest.mark.parametrize("field", _FIELDS)
def test_three_path_default_access(field: str) -> None:
    expected = CorrectionsSettingsModel().model_dump()[field]
    assert_three_path_access("corrections", field, expected)


def test_known_org_phrases_read() -> None:
    phrases = AnalysisConfig().corrections.known_org_phrases["REN21"]
    assert phrases == ["ren twenty one", "wren twenty one"]


def test_known_org_phrases_whole_dict_assign() -> None:
    cfg = AnalysisConfig()
    new_phrases = {"REN21": ["alpha"], "ACME": ["beta"]}
    setattr(cfg.corrections, "known_org_phrases", new_phrases)
    assert cfg.corrections.known_org_phrases == new_phrases
    tx = TranscriptXConfig()
    tx.analysis.corrections.known_org_phrases = new_phrases
    assert tx.to_dict()["analysis"]["corrections"]["known_org_phrases"] == new_phrases


def test_known_org_phrases_deep_list_mutation() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.corrections.known_org_phrases["REN21"].append("extra phrase")
    assert "extra phrase" in cfg.analysis.corrections.known_org_phrases["REN21"]
    assert (
        "extra phrase"
        in cfg.to_dict()["analysis"]["corrections"]["known_org_phrases"]["REN21"]
    )


def test_file_override_known_org_phrases_partial_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    before = asdict(cfg.analysis.corrections)["known_org_phrases"]
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "analysis": {
                    "corrections": {
                        "known_org_phrases": {"REN21": ["only one"]},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    after = cfg.analysis.corrections.known_org_phrases
    assert after["REN21"] == ["only one"]
    assert after != before


def test_file_override_corrections_partial_scalar_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {"analysis": {"corrections": {"consistency_similarity_threshold": 0.91}}}
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.corrections.consistency_similarity_threshold == 0.91
    assert cfg.analysis.corrections.fuzzy_similarity_threshold == 0.92


def test_setattr_accepts_value_pydantic_would_reject_at_validation_boundary() -> None:
    cfg = AnalysisConfig()
    setattr(cfg.corrections, "consistency_similarity_threshold", "high")
    assert cfg.corrections.consistency_similarity_threshold == "high"
    errors = validate_config(
        {
            "analysis": {
                "corrections": {"consistency_similarity_threshold": "high"},
            }
        }
    )
    assert "analysis.corrections.consistency_similarity_threshold" in errors


def test_validate_config_invalid_payload_rejected() -> None:
    errors = validate_config(
        {"analysis": {"corrections": {"consistency_similarity_threshold": "high"}}}
    )
    assert "analysis.corrections.consistency_similarity_threshold" in errors


def test_is_dataclass_compatible_for_file_overrides() -> None:
    assert_is_dataclass_subtree("corrections")
