"""Artifact contract defaults and overrides."""

from __future__ import annotations

import pytest

from transcriptx.core.pipeline.module_artifact_contracts import (
    ModuleArtifactContract,
    get_artifact_contract,
)


@pytest.mark.unit
def test_get_artifact_contract_corrections_override() -> None:
    c = get_artifact_contract("corrections")
    assert c.expects_artifacts == "conditional"
    assert c.artifact_mode == "report_only"
    assert c.missing_artifacts_affects_status == "ignore"


@pytest.mark.unit
def test_get_artifact_contract_known_module_uses_registry_category() -> None:
    c = get_artifact_contract("stats")
    assert isinstance(c, ModuleArtifactContract)
    assert c.expects_artifacts == "yes"
    assert c.artifact_mode == "files"


@pytest.mark.unit
def test_get_artifact_contract_unknown_module_falls_back_to_medium() -> None:
    c = get_artifact_contract("definitely_not_a_real_module_id_xyz")
    assert c.expects_artifacts == "yes"
    assert c.artifact_mode == "files"
    assert c.missing_artifacts_affects_status == "warn"
