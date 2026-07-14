"""Tests for group key."""

from transcriptx.core.domain.group import Group


def test_group_key_is_deterministic_for_same_order() -> None:
    uuids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    first = Group.compute_key(uuids)
    second = Group.compute_key(uuids)
    assert first == second
    assert first.startswith("grp_v1_")


def test_group_key_changes_for_different_order() -> None:
    uuids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    forward = Group.compute_key(uuids)
    reversed_key = Group.compute_key(list(reversed(uuids)))
    assert forward != reversed_key


def test_group_key_empty_and_single_member() -> None:
    empty = Group.compute_key([])
    assert empty.startswith("grp_v1_")
    assert empty == Group.compute_key([])

    single = Group.compute_key(["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"])
    assert single.startswith("grp_v1_")
    assert single != empty


def test_group_key_normalizes_whitespace_and_case() -> None:
    raw = ["  AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA  "]
    cleaned = ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
    assert Group.compute_key(raw) == Group.compute_key(cleaned)
