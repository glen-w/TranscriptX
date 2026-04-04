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
