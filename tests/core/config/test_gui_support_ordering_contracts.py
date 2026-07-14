"""Tests for gui support ordering contracts."""

from __future__ import annotations

from transcriptx.core.config import (
    list_runtime_profile_targets,
    list_supported_profile_target_ids,
)
from transcriptx.core.config.gui_support import PROFILE_TARGET_SUPPORT


def test_supported_target_ids_are_unique_and_stable() -> None:
    target_ids = list_supported_profile_target_ids()
    assert len(target_ids) == len(set(target_ids))
    assert target_ids[0] == "workflow"


def test_supported_target_ids_cover_support_map() -> None:
    target_ids = set(list_supported_profile_target_ids())
    assert target_ids == set(PROFILE_TARGET_SUPPORT.keys())


def test_runtime_targets_keep_declared_order_subset() -> None:
    runtime_ids = [t.target_id for t in list_runtime_profile_targets()]
    supported = list(list_supported_profile_target_ids())
    positions = [supported.index(target_id) for target_id in runtime_ids]
    assert positions == sorted(positions)


def test_all_runtime_targets_are_flagged_runtime_loaded() -> None:
    assert all(target.runtime_loaded for target in list_runtime_profile_targets())
